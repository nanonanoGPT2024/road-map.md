# app/controllers/tenants/settings_controller.rb
# frozen_string_literal: true

module Tenants
  class SettingsController < ActionController::API
    before_action :set_tenant!

    def update
      if @current_tenant.update(secure_tenant_params)
        render json: { status: "success", data: @current_tenant }
      else
        render json: { status: "error", errors: @current_tenant.errors.full_messages }, 
               status: :unprocessable_entity
      end
    end

    private

    def set_tenant!
      @current_tenant = Tenant.find_by!(slug: request.subdomain)
    end

    # Strong Parameters dengan Nested Attributes Dinamis dan Strict Type Permitting
    def secure_tenant_params
      params.require(:tenant).permit(
        :company_name,
        :timezone,
        contact_attributes: %i[id email phone _destroy],
        notification_preferences: {}, # Mengizinkan skema arbitrary Hash key-value
        metadata_tags: []             # Mengizinkan scalar array
      ).tap do |whitelisted|
        # Injeksi runtime validation parameter jika diperlukan
        if whitelisted[:notification_preferences].present?
          whitelisted[:notification_preferences] = whitelisted[:notification_preferences].permit(
            :email_digest, :slack_webhook_url, :sms_urgent
          )
        end
      end
    end
  end
end
