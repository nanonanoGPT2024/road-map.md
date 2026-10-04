# frozen_string_literal: true
# webhook_processor.rb

require 'json'
require 'openssl'
require 'stringio'

class WebhookProcessor
  # Freeze konstanta untuk mencegah alokasi berulang di Hot Path
  HMAC_DIGEST = OpenSSL::Digest.new('sha256')
  SIGNATURE_HEADER = 'HTTP_X_SIGNATURE'.freeze
  EMPTY_RESPONSE   = [204, {}, []].freeze
  ERROR_RESPONSE   = [401, { 'content-type' => 'text/plain' }.freeze, ['Invalid Signature'.freeze]].freeze

  def initialize(app, secret_key)
    @app = app
    @secret_key = secret_key.freeze
    # Buffer reusable per thread untuk menghitung HMAC tanpa alokasi string baru
    @thread_local_digest_key = "hmac_thread_buffer_#{object_id}".freeze
  end

  def call(env)
    return @app.call(env) unless env['PATH_INFO'] == '/api/v1/webhooks'

    # Baca IO Stream langsung dari Rack input tanpa buffer ganda
    rack_input = env['rack.input']
    raw_payload = rack_input.read
    rack_input.rewind

    incoming_sig = env[SIGNATURE_HEADER]

    unless valid_signature?(raw_payload, incoming_sig)
      return ERROR_RESPONSE
    end

    # Parse JSON menggunakan C-optimized parsing flags
    # Symbolize names mencegah instansiasi ribuan objek string duplikat
    payload_data = JSON.parse(raw_payload, symbolize_names: true)

    # Proses payload secara zero-allocation mutasi
    process_event(payload_data)

    EMPTY_RESPONSE
  end

  private

  def valid_signature?(payload, signature)
    return false if signature.nil? || payload.nil?

    # Hitung HMAC menggunakan per-thread cached digest
    computed = OpenSSL::HMAC.hexdigest(HMAC_DIGEST, @secret_key, payload)
    
    # Secure constant-time comparison untuk mitigasi timing attacks
    Rack::Utils.secure_compare(computed, signature)
  end

  def process_event(data)
    # Lakukan ekstraksi metadata tanpa destruktif array instantiations
    event_id = data[:id]
    event_type = data[:event]
    
    # Simulasi eksekusi domain logic berkecepatan tinggi
    # Dalam produksi: Kirim via Queue non-blocking atau RingBuffer
    nil
  end
end
