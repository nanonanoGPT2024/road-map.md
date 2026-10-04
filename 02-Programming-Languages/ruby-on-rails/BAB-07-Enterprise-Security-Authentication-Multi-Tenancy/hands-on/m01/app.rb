# app/controllers/auth/saml_sessions_controller.rb
module Auth
  class SamlSessionsController < ActionController::Base
    protect_from_forgery except: :consume # SAML POST berasal dari IdP eksternal

    # Inisiasi SSO: Redirect ke Okta/Azure AD
    def create
      tenant = Tenant.find_by!(subdomain: params[:subdomain])
      saml_request = OneLogin::RubySaml::Authrequest.new
      redirect_to saml_request.create(saml_settings_for(tenant)), allow_other_host: true
    end

    # Assertion Consumer Service (ACS) Endpoint
    def consume
      tenant = Tenant.find_by!(id: params[:RelayState])
      response = OneLogin::RubySaml::Response.new(
        params[:SAMLResponse],
        settings: saml_settings_for(tenant)
      )

      if response.is_valid?
        user = find_or_provision_user(tenant, response)
        
        # Rotasi Session Fixation ID
        reset_session
        
        session[:user_id] = user.id
        session[:tenant_id] = tenant.id
        session[:last_authenticated_at] = Time.current.to_i

        redirect_to dashboard_url(subdomain: tenant.subdomain), notice: "SSO Login Berhasil"
      else
        Rails.logger.error("SAML Validation Failure: #{response.errors}")
        render json: { error: "SAML Signature Invalid", details: response.errors }, status: :unauthorized
      end
    end

    private

    def saml_settings_for(tenant)
      settings = OneLogin::RubySaml::Settings.new
      settings.assertion_consumer_service_url = auth_saml_consume_url(subdomain: tenant.subdomain)
      settings.issuer                         = "globalledger-sp-entity-id"
      settings.idp_sso_target_url             = tenant.saml_issuer
      settings.idp_cert                       = tenant.saml_certificate
      settings.name_identifier_format         = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
      settings
    end

    def find_or_provision_user(tenant, saml_response)
      email = saml_response.nameid
      user = nil

      # Eksekusi write dalam database scope tenant
      TenantDatabaseScope.isolate(tenant) do
        user = User.find_or_initialize_by(email: email, tenant_id: tenant.id)
        user.first_name = saml_response.attributes["firstName"] || "Corporate"
        user.last_name  = saml_response.attributes["lastName"]  || "User"
        user.save!
      end

      user
    end
  end
end
