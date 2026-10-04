# frozen_string_literal: true

require 'time'
require 'securerandom'

module CoreEntity
  # Error hierarchy untuk domain model
  class Error < StandardError; end
  class ValidationError < Error; end
  class ImmutableAttributeError < Error; end

  # Type System & Coercion Engine
  module Types
    class BaseType
      def coerce(val)
        val
      end

      def valid?(_val)
        true
      end
    end

    class StringType < BaseType
      def coerce(val)
        val&.to_s
      end

      def valid?(val)
        val.is_a?(String)
      end
    end

    class IntegerType < BaseType
      def coerce(val)
        return nil if val.nil?
        Integer(val)
      rescue ArgumentError, TypeError
        raise ValidationError, "Nilai '#{val}' tidak valid untuk Integer"
      end

      def valid?(val)
        val.is_a?(Integer)
      end
    end

    class BooleanType < BaseType
      def coerce(val)
        return nil if val.nil?
        [true, 1, '1', 't', 'true'].include?(val.is_a?(String) ? val.downcase : val)
      end

      def valid?(val)
        val.is_a?(TrueClass) || val.is_a?(FalseClass)
      end
    end

    STRING = StringType.new
    INTEGER = IntegerType.new
    BOOLEAN = BooleanType.new
  end

  # Modul Inti Metamodel
  module Model
    def self.included(base)
      base.extend(ClassMethods)
      base.include(InstanceMethods)
      
      # Inisialisasi metadata pada class yang menyematkan modul ini
      base.instance_variable_set(:@attributes_schema, {})
      base.instance_variable_set(:@primary_key_attr, nil)
    end

    module ClassMethods
      attr_reader :attributes_schema, :primary_key_attr

      # Macro DSL untuk registrasi atribut
      def attribute(name, type, default: nil, readonly: false)
        attr_name = name.to_sym
        
        # Validasi duplikasi
        if @attributes_schema.key?(attr_name)
          raise ArgumentError, "Atribut '#{attr_name}' sudah terdaftar pada #{self}."
        end

        # Registrasi ke skema
        @attributes_schema[attr_name] = {
          type: type,
          default: default,
          readonly: readonly
        }.freeze

        # Compile accessors secara dinamis (Zero runtime lookup overhead)
        compile_reader(attr_name)
        compile_writer(attr_name, readonly)
      end

      def primary_key(name)
        @primary_key_attr = name.to_sym
        attribute(name, Types::STRING, default: -> { SecureRandom.uuid }, readonly: true)
      end

      private

      def compile_reader(name)
        define_method(name) do
          @attributes[name]
        end
      end

      def compile_writer(name, readonly)
        if readonly
          define_method("#{name}=") do |_value|
            raise ImmutableAttributeError, "Atribut readonly '#{name}' tidak dapat dimutasi setelah inisialisasi"
          end
        else
          define_method("#{name}=") do |value|
            write_attribute(name, value)
          end
        end
      end
    end

    module InstanceMethods
      attr_reader :mutations

      def initialize(initial_attributes = {})
        @attributes = {}
        @mutations = {}
        @initialized = false

        apply_defaults
        hydrate(initial_attributes)
        @initialized = true
      end

      def dirty?
        !@mutations.empty?
      end

      def changed_attributes
        @mutations.dup.freeze
      end

      def to_h
        @attributes.dup.freeze
      end

      def inspect
        attrs = @attributes.map { |k, v| "#{k}: #{v.inspect}" }.join(', ')
        "#<#{self.class.name} #{attrs} [dirty: #{dirty?}]>"
      end

      private

      def apply_defaults
        self.class.attributes_schema.each do |name, config|
          default_val = config[:default]
          resolved_val = default_val.is_a?(Proc) ? default_val.call : default_val
          @attributes[name] = resolved_val unless resolved_val.nil?
        end
      end

      def hydrate(hash)
        hash.each do |key, raw_value|
          attr_sym = key.to_sym
          schema = self.class.attributes_schema[attr_sym]
          
          next unless schema # Abaikan atribut yang tidak didefinisikan

          coerced_value = schema[:type].coerce(raw_value)
          @attributes[attr_sym] = coerced_value
        end
      end

      def write_attribute(name, value)
        schema = self.class.attributes_schema.fetch(name) do
          raise ArgumentError, "Atribut '#{name}' tidak dikenal."
        end

        coerced = schema[:type].coerce(value)
        return if @attributes[name] == coerced

        # Catat original value untuk dirty tracking
        @mutations[name] = @attributes[name] unless @mutations.key?(name)
        @attributes[name] = coerced
      end
    end
  end
end

# -------------------------------------------------------------
# Domain Implementation: Enterprise Ledger & Account System
# -------------------------------------------------------------

class LedgerTransaction
  include CoreEntity::Model

  primary_key :transaction_id
  attribute :reference_number, CoreEntity::Types::STRING
  attribute :amount_cents,      CoreEntity::Types::INTEGER
  attribute :is_settled,       CoreEntity::Types::BOOLEAN, default: false
  attribute :cleared_at,       CoreEntity::Types::STRING,  default: nil
end

# Verification & Test Suite
if __FILE__ == $PROGRAM_NAME
  puts "================================================="
  puts "SISTEM PRODUCTION LEDGER TRANSACTION ENGINE"
  puts "================================================="

  # 1. Inisialisasi Objek dengan Defaults dan Primary Key Generasi
  tx = LedgerTransaction.new(
    reference_number: "TRX-PAY-2026-9901",
    amount_cents: "500000" # Coercion dari String ke Integer
  )

  puts "\n[STEP 1: Instansiasi]"
  puts tx.inspect
  puts "Transaction ID (Auto-generated UUID): #{tx.transaction_id}"
  puts "Settled status (Default): #{tx.is_settled}"
  puts "Amount Cents (Coerced): #{tx.amount_cents} (Class: #{tx.amount_cents.class})"
  puts "Is Dirty?: #{tx.dirty?}"

  # 2. Mutasi State (Dirty Tracking)
  puts "\n[STEP 2: Mutasi Atribut]"
  tx.amount_cents = 750000
  tx.is_settled = "true" # Coercion dari string ke boolean

  puts tx.inspect
  puts "Is Dirty?: #{tx.dirty?}"
  puts "Mutations Tracked: #{tx.changed_attributes.inspect}"

  # 3. Pengujian Proteksi Read-Only (Enkapsulasi)
  puts "\n[STEP 3: Proteksi Enkapsulasi Readonly]"
  begin
    tx.transaction_id = "MANUAL-OVERRIDE-ATTEMPT"
  rescue CoreEntity::ImmutableAttributeError => e
    puts "BERHASIL: Proteksi Immutable Attribute memblokir aksi! Pesan: #{e.message}"
  end

  # 4. Pengujian Validasi Tipe
  puts "\n[STEP 4: Type Coercion Safety Boundary]"
  begin
    tx.amount_cents = "INI_BUKAN_ANGKA"
  rescue CoreEntity::ValidationError => e
    puts "BERHASIL: Type enforcement menggagalkan data invalid! Pesan: #{e.message}"
  end
end
