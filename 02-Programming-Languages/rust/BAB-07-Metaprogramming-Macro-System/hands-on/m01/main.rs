use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::quote;
use syn::{
    parse_macro_input, Data, DeriveInput, Fields, LitInt, Meta,
};

#[proc_macro_derive(ValidateRange, attributes(range))]
pub fn derive_validate_range(input: TokenStream) -> TokenStream {
    // Parsing TokenStream mentah menjadi AST Rust menggunakan syn
    let input = parse_macro_input!(input as DeriveInput);

    let struct_name = &input.ident;
    let validations = generate_field_validations(&input.data);

    // Sintesis kode implementasi menggunakan quote
    let expanded = quote! {
        impl RuntimeValidator for #struct_name {
            fn validate(&self) -> Result<(), String> {
                #validations
                Ok(())
            }
        }
    };

    // Mengembalikan hasil konversi TokenStream2 kembali ke proc_macro::TokenStream
    TokenStream::from(expanded)
}

fn generate_field_validations(data: &Data) -> TokenStream2 {
    let fields = match data {
        Data::Struct(data_struct) => match &data_struct.fields {
            Fields::Named(fields_named) => &fields_named.named,
            _ => panic!("ValidateRange hanya mendukung Named Structs"),
        },
        _ => panic!("ValidateRange hanya dapat digunakan pada Struct"),
    };

    let mut checks = Vec::new();

    for field in fields {
        let field_name = match &field.ident {
            Some(ident) => ident,
            None => continue,
        };

        for attr in &field.attrs {
            if !attr.path().is_ident("range") {
                continue;
            }

            let mut min_val: Option<i64> = None;
            let mut max_val: Option<i64> = None;

            // Parsing nested meta attributes #[range(min = 1, max = 10)]
            if let Err(err) = attr.parse_nested_meta(|meta| {
                if meta.path.is_ident("min") {
                    let value = meta.value()?;
                    let lit: LitInt = value.parse()?;
                    min_val = Some(lit.base10_parse::<i64>()?);
                    Ok(())
                } else if meta.path.is_ident("max") {
                    let value = meta.value()?;
                    let lit: LitInt = value.parse()?;
                    max_val = Some(lit.base10_parse::<i64>()?);
                    Ok(())
                } else {
                    Err(meta.error("Atribut range tidak didukung (gunakan 'min' atau 'max')"))
                }
            }) {
                panic!("Gagal mem-parsing atribut #[range]: {}", err);
            }

            let field_str = field_name.to_string();

            if let Some(min) = min_val {
                checks.push(quote! {
                    if (self.#field_name as i64) < #min {
                        return Err(format!(
                            "Validasi gagal: Field '{}' bernilai {}, batas minimum {}",
                            #field_str, self.#field_name, #min
                        ));
                    }
                });
            }

            if let Some(max) = max_val {
                checks.push(quote! {
                    if (self.#field_name as i64) > #max {
                        return Err(format!(
                            "Validasi gagal: Field '{}' bernilai {}, batas maksimum {}",
                            #field_str, self.#field_name, #max
                        ));
                    }
                });
            }
        }
    }

    quote! {
        #( #checks )*
    }
}
