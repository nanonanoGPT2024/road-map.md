// Path: src/EnterpriseBilling.Domain/Entities/Invoice.cs
namespace EnterpriseBilling.Domain.Entities;

using EnterpriseBilling.Domain.Common;

public enum InvoiceStatus { Draft = 1, Issued = 2, Paid = 3, Cancelled = 4 }

public sealed class Invoice
{
    public Guid Id { get; private set; }
    public string InvoiceNumber { get; private set; } = null!;
    public string CustomerTaxId { get; private set; } = null!;
    public decimal TotalAmount { get; private set; }
    public InvoiceStatus Status { get; private set; }
    public DateTime IssuedAtUtc { get; private set; }

    private Invoice() { } // Ef Core

    public static Result<Invoice> CreateDraft(string invoiceNumber, string customerTaxId, decimal amount)
    {
        if (string.IsNullOrWhiteSpace(invoiceNumber))
            return Result.Failure<Invoice>("Nomor faktur tidak boleh kosong.");

        if (string.IsNullOrWhiteSpace(customerTaxId))
            return Result.Failure<Invoice>("NPWP/Customer Tax ID tidak valid.");

        if (amount <= 0)
            return Result.Failure<Invoice>("Nilai tagihan faktur harus lebih besar dari 0.");

        var invoice = new Invoice
        {
            Id = Guid.NewGuid(),
            InvoiceNumber = invoiceNumber,
            CustomerTaxId = customerTaxId,
            TotalAmount = amount,
            Status = InvoiceStatus.Draft
        };

        return Result.Success(invoice);
    }

    public Result Issue(DateTime currentUtc)
    {
        if (Status != InvoiceStatus.Draft)
            return Result.Failure($"Faktur tidak dapat diterbitkan karena berstatus: {Status}.");

        Status = InvoiceStatus.Issued;
        IssuedAtUtc = currentUtc;

        return Result.Success();
    }
}
