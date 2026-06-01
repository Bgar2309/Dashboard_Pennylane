// Badge « Payé (banque) » — apposé sur les clients dont une facture est déjà
// couverte par un paiement rapproché (blocked_by_payment). Ces clients sont
// sortis de la liste à relancer.

export function PaymentBadge() {
  return (
    <span className="paybadge" title="Couvert par un paiement bancaire rapproché">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M5 13l4 4L19 7"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Payé (banque)
    </span>
  );
}
