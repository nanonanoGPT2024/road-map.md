# Hitung konkurensi berbasis alokasi container vCPU
threads_count = ENV.fetch("RAILS_MAX_THREADS") { 3 }
threads threads_count, threads_count

# Bind langsung ke Unix port yang diekspos ke Thruster
port ENV.fetch("PORT") { 3000 }

# Puma Clustered Mode untuk konkurensi multi-core di dalam kontainer
workers ENV.fetch("WEB_CONCURRENCY") { 2 }

# Gunakan Worker Timeout yang memadai untuk slow requests sebelum kamal-proxy cut-off
worker_timeout 30

# Mekanisme pre-forking untuk efisiensi copy-on-write memory
preload_app!

# SRE Best Practice: Connection Pool Management
on_worker_boot do
  ActiveSupport.on_load(:active_record) do
    ActiveRecord::Base.establish_connection
  end
end

# Graceful Termination Handlers
on_worker_shutdown do
  ActiveSupport.on_load(:active_record) do
    ActiveRecord::Base.connection_pool.disconnect!
  end
end
