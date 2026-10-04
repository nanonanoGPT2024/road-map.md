# super_fast_math/super_fast_math.gemspec
Gem::Specification.new do |spec|
  spec.name          = "super_fast_math"
  spec.version       = "0.1.0"
  spec.authors       = ["Principal Architect"]
  spec.email         = ["architect@enterprise.internal"]
  spec.summary       = "High-performance native computing gem"
  spec.license       = "MIT"
  spec.files         = Dir["lib/**/*.rb", "ext/**/*.{c,h,rb}", "sig/**/*.rbs"]
  spec.extensions    = ["ext/super_fast_math/extconf.rb"]
  spec.require_paths = ["lib"]
  spec.required_ruby_version = ">= 3.0.0"
end
