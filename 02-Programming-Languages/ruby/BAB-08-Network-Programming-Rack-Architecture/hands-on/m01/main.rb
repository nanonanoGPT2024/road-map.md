# server.rb
require 'socket'
require 'stringio'

class MinimalRackServer
  CRLF = "\r\n"

  def initialize(app, host: '127.0.0.1', port: 9292, pool_size: 8)
    @app = app
    @host = host
    @port = port
    @pool_size = pool_size
    @queue = Thread::Queue.new
    @threads = []
    @running = false
  end

  def start
    @server = TCPServer.new(@host, @port)
    @server.setsockopt(Socket::SOL_SOCKET, Socket::SO_REUSEADDR, true)
    @running = true

    puts "[Server] Mendengarkan di http://#{@host}:#{@port} dengan #{@pool_size} threads..."
    spawn_worker_pool

    while @running
      begin
        socket = @server.accept
        @queue.push(socket)
      rescue IOError, Errno::EBADF
        break # Server dimatikan
      end
    end
  end

  def stop
    @running = false
    @server.close if @server && !@server.closed?
    @pool_size.times { @queue.push(:shutdown) }
    @threads.each(&:join)
    puts "[Server] Berhenti secara bersih."
  end

  private

  def spawn_worker_pool
    @pool_size.times do
      @threads << Thread.new do
        loop do
          socket = @queue.pop
          break if socket == :shutdown

          handle_connection(socket)
        end
      end
    end
  end

  def handle_connection(socket)
    request_line = socket.gets(CRLF)
    if request_line.nil?
      socket.close
      return
    end

    method, full_path, http_version = request_line.strip.split(' ', 3)
    path, query_string = full_path.split('?', 2)

    headers = {}
    while (line = socket.gets(CRLF))
      clean_line = line.strip
      break if clean_line.empty?

      key, value = clean_line.split(':', 2)
      headers[key.strip.downcase] = value.strip
    end

    content_length = headers['content-length'].to_i
    body_data = content_length > 0 ? socket.read(content_length) : ""
    rack_input = StringIO.new(body_data)

    env = build_rack_env(method, path, query_string, headers, rack_input, socket)

    status, response_headers, response_body = @app.call(env)

    send_response(socket, status, response_headers, response_body)
  rescue StandardError => e
    warn "[Error] Exception ditangkap: #{e.message}\n#{e.backtrace.join("\n")}"
    send_error_response(socket, 500, "Internal Server Error")
  ensure
    socket.close unless socket.closed?
  end

  def build_rack_env(method, path, query_string, headers, rack_input, socket)
    rack_env = {
      'REQUEST_METHOD'    => method,
      'SCRIPT_NAME'       => '',
      'PATH_INFO'         => path,
      'QUERY_STRING'      => query_string || '',
      'SERVER_NAME'       => @host,
      'SERVER_PORT'       => @port.to_s,
      'HTTP_VERSION'      => 'HTTP/1.1',
      'rack.version'      => [3, 0],
      'rack.input'        => rack_input,
      'rack.errors'       => $stderr,
      'rack.multithread'  => true,
      'rack.multiprocess' => false,
      'rack.run_once'     => false,
      'rack.url_scheme'   => 'http'
    }

    headers.each do |key, value|
      cgi_key = "HTTP_" + key.upcase.tr('-', '_')
      cgi_key = 'CONTENT_TYPE' if key == 'content-type'
      cgi_key = 'CONTENT_LENGTH' if key == 'content-length'
      rack_env[cgi_key] = value
    end

    rack_env
  end

  def send_response(socket, status, headers, body)
    status_text = status == 200 ? "OK" : "Status #{status}"
    socket.write("HTTP/1.1 #{status} #{status_text}#{CRLF}")

    headers_hash = headers.to_h
    headers_hash['connection'] ||= 'close'

    headers_hash.each do |k, v|
      socket.write("#{k}: #{v}#{CRLF}")
    end
    socket.write(CRLF)

    body.each do |chunk|
      socket.write(chunk)
    end
  ensure
    body.close if body.respond_to?(:close)
  end

  def send_error_response(socket, status, message)
    response_body = "#{status} #{message}\n"
    socket.write("HTTP/1.1 #{status} #{message}#{CRLF}")
    socket.write("content-type: text/plain#{CRLF}")
    socket.write("content-length: #{response_body.bytesize}#{CRLF}")
    socket.write("connection: close#{CRLF}#{CRLF}")
    socket.write(response_body)
  end
end
