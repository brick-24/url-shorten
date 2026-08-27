document.addEventListener("DOMContentLoaded", () => {
  const qrContainer = document.getElementById("qr-code");

  if (!qrContainer) {
    return;
  }

  const url = qrContainer.dataset.url;

  if (!url) {
    console.error("QR code: no URL provided.");
    return;
  }

  if (typeof QRCode === "undefined") {
    console.error("QR code: QRCode library failed to load.");
    return;
  }

  new QRCode(qrContainer, {
    text: url,
    width: 96,
    height: 96,
    correctLevel: QRCode.CorrectLevel.M,
  });
});
