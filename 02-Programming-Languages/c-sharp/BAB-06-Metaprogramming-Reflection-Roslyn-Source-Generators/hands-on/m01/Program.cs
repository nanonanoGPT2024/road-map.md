using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace PaymentMapper.Generators;

// Model Equatable murni untuk caching Roslyn
public readonly record struct PropertyMappingModel(string SourcePropertyName, string TargetPropertyName);

public readonly record struct MapperDescriptor(
    string Namespace,
    string SourceTypeName,
    string TargetTypeName,
    EquatableArray<PropertyMappingModel> Properties) : IEquatable<MapperDescriptor>;

// Wrapper list untuk menjamin immutability & equality comparison yang benar
public readonly struct EquatableArray<T> : IEquatable<EquatableArray<T>> where T : IEquatable<T>
{
    private readonly T[]? _items;
    public EquatableArray(T[] items) => _items = items;
    public T[] Items => _items ?? Array.Empty<T>();

    public bool Equals(EquatableArray<T> other)
    {
        if (_items is null && other._items is null) return true;
        if (_items is null || other._items is null) return false;
        if (_items.Length != other._items.Length) return false;
        for (int i = 0; i < _items.Length; i++)
        {
            if (!_items[i].Equals(other._items[i])) return false;
        }
        return true;
    }

    public override bool Equals(object? obj) => obj is EquatableArray<T> other && Equals(other);
    public override int GetHashCode()
    {
        if (_items is null) return 0;
        int hash = 17;
        foreach (var item in _items) hash = hash * 31 + item.GetHashCode();
        return hash;
    }
}

[Generator]
public sealed class HighPerformanceMapperGenerator : IIncrementalGenerator
{
    private const string AttributeNamespace = "PaymentService.Domain.Attributes";
    private const string AttributeName = "GenerateMapperAttribute";

    public void Initialize(IncrementalGeneratorInitializationContext context)
    {
        // 1. Ekstraksi sintaksis kandidat tipe yang memiliki atribut
        IncrementalValuesProvider<ClassDeclarationSyntax> candidateClasses = context.SyntaxProvider
            .CreateSyntaxProvider(
                predicate: static (node, _) => node is ClassDeclarationSyntax { AttributeLists.Count: > 0 },
                transform: static (ctx, _) => (ClassDeclarationSyntax)ctx.Node
            );

        // 2. Gabungkan dengan SemanticModel untuk filter ketat simbol dan ekstraksi data model
        IncrementalValuesProvider<MapperDescriptor?> mapperDescriptors = candidateClasses
            .Combine(context.CompilationProvider)
            .Select(static (combined, cancellationToken) =>
            {
                var (classSyntax, compilation) = combined;
                SemanticModel semanticModel = compilation.GetSemanticModel(classSyntax.SyntaxTree);
                
                if (semanticModel.GetDeclaredSymbol(classSyntax, cancellationToken) is not INamedTypeSymbol sourceSymbol)
                    return null;

                // Cari atribut GenerateMapperAttribute
                AttributeData? mapperAttribute = sourceSymbol.GetAttributes().FirstOrDefault(ad =>
                {
                    INamedTypeSymbol? attrClass = ad.AttributeClass;
                    return attrClass != null &&
                           attrClass.Name == AttributeName &&
                           attrClass.ContainingNamespace.ToDisplayString() == AttributeNamespace;
                });

                if (mapperAttribute is null || mapperAttribute.ConstructorArguments.Length == 0)
                    return null;

                // Tipe target pemetaan dari argumen konstruktor
                if (mapperAttribute.ConstructorArguments[0].Value is not INamedTypeSymbol targetSymbol)
                    return null;

                // Ambil daftar properti publik yang cocok antara source dan target
                var sourceProps = sourceSymbol.GetMembers().OfType<IPropertySymbol>()
                    .Where(p => p.GetMethod != null && p.DeclaredAccessibility == Accessibility.Public);

                var targetProps = targetSymbol.GetMembers().OfType<IPropertySymbol>()
                    .Where(p => p.SetMethod != null && p.DeclaredAccessibility == Accessibility.Public)
                    .ToDictionary(p => p.Name, StringComparer.Ordinal);

                List<PropertyMappingModel> mappings = new();
                foreach (var sProp in sourceProps)
                {
                    if (targetProps.TryGetValue(sProp.Name, out var tProp))
                    {
                        // Pastikan tipenya kompatibel
                        if (SymbolEqualityComparer.Default.Equals(sProp.Type, tProp.Type))
                        {
                            mappings.Add(new PropertyMappingModel(sProp.Name, tProp.Name));
                        }
                    }
                }

                string ns = sourceSymbol.ContainingNamespace.IsGlobalNamespace
                    ? "Global"
                    : sourceSymbol.ContainingNamespace.ToDisplayString();

                return new MapperDescriptor(
                    ns,
                    sourceSymbol.Name,
                    targetSymbol.ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat),
                    new EquatableArray<PropertyMappingModel>(mappings.ToArray())
                );
            })
            .Where(static descriptor => descriptor is not null);

        // 3. Emit Source Code
        context.RegisterSourceOutput(mapperDescriptors, static (spc, descriptor) =>
        {
            if (descriptor is null) return;

            MapperDescriptor model = descriptor.Value;
            StringBuilder sb = new();

            sb.AppendLine("// <auto-generated/>");
            sb.AppendLine("#nullable enable");
            sb.AppendLine("using System;");
            sb.AppendLine();
            sb.AppendLine($"namespace {model.Namespace}");
            sb.AppendLine("{");
            sb.AppendLine($"    public static class {model.SourceTypeName}MapperExtensions");
            sb.AppendLine("    {");
            sb.AppendLine($"        public static {model.TargetTypeName} MapToDomain(this {model.SourceTypeName} source)");
            sb.AppendLine("        {");
            sb.AppendLine("            if (source is null) throw new ArgumentNullException(nameof(source));");
            sb.AppendLine($"            return new {model.TargetTypeName}");
            sb.AppendLine("            {");

            foreach (var prop in model.Properties.Items)
            {
                sb.AppendLine($"                {prop.TargetPropertyName} = source.{prop.SourcePropertyName},");
            }

            sb.AppendLine("            };");
            sb.AppendLine("        }");
            sb.AppendLine("    }");
            sb.AppendLine("}");

            spc.AddSource($"{model.SourceTypeName}_To_DomainMapper.g.cs", SourceText.From(sb.ToString(), Encoding.UTF8));
        });
    }
}
