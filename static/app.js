const form = document.querySelector("#warranty-form");
const toast = document.querySelector("#success-toast");
const closeToast = toast.querySelector("button");
const purchaseDate = form.elements.purchase_date;

const today = new Date();
const localToday = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
  .toISOString()
  .split("T")[0];
purchaseDate.max = localToday;

const messages = {
  full_name: "Vui lòng nhập họ và tên.",
  phone: "Vui lòng nhập số điện thoại hợp lệ.",
  address: "Vui lòng nhập địa chỉ.",
  model: "Vui lòng nhập sản phẩm.",
  purchase_date: "Vui lòng chọn ngày mua hợp lệ."
};

function isValid(field) {
  const value = field.value.trim();
  if (!value) return false;
  if (field.name === "phone") return /^(0|\+84)[0-9]{9,10}$/.test(value.replace(/[ .-]/g, ""));
  if (field.name === "purchase_date") return value <= localToday;
  return true;
}

function validateField(field) {
  const container = field.closest(".field");
  const error = container.querySelector(".error-message");
  const valid = isValid(field);
  container.classList.toggle("invalid", !valid);
  field.setAttribute("aria-invalid", String(!valid));
  if (error) error.textContent = valid ? "" : messages[field.name];
  return valid;
}

form.querySelectorAll("[required]").forEach((field) => {
  field.addEventListener("blur", () => validateField(field));
  field.addEventListener("input", () => {
    if (field.closest(".field").classList.contains("invalid")) validateField(field);
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const requiredFields = [...form.querySelectorAll("[required]")];
  const valid = requiredFields.map(validateField).every(Boolean);

  if (!valid) {
    requiredFields.find((field) => field.getAttribute("aria-invalid") === "true")?.focus();
    return;
  }

  const submitButton = form.querySelector("button[type='submit']");
  const originalText = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Đang lưu...";

  try {
    const data = Object.fromEntries(new FormData(form).entries());
    data.product = data.model;
    delete data.model;

    const response = await fetch("/api/warranties", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Không thể lưu thông tin.");

    toast.querySelector(".toast-icon").textContent = "✓";
    toast.querySelector("strong").textContent = "Kích hoạt thành công!";
    toast.querySelector("p").textContent = "Abraham Bike đã ghi nhận thông tin của bạn.";
    toast.classList.remove("error");
    toast.classList.add("show");
    form.reset();
    setTimeout(() => toast.classList.remove("show"), 5000);
  } catch (error) {
    toast.querySelector(".toast-icon").textContent = "!";
    toast.querySelector("strong").textContent = "Chưa thể gửi thông tin";
    toast.querySelector("p").textContent = error.message;
    toast.classList.add("error", "show");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalText;
  }
});

closeToast.addEventListener("click", () => toast.classList.remove("show"));

const pageShell = document.querySelector(".page-shell");

function fitPageToViewport() {
  const viewport = window.visualViewport;
  const width = viewport?.width ?? window.innerWidth;
  const height = viewport?.height ?? window.innerHeight;
  const scale = Math.min(
    1,
    Math.max(1, width - 24) / pageShell.offsetWidth,
    Math.max(1, height - 24) / pageShell.offsetHeight
  );
  pageShell.style.setProperty("--viewport-scale", String(scale));
  pageShell.style.left = `${(viewport?.offsetLeft ?? 0) + width / 2}px`;
  pageShell.style.top = `${(viewport?.offsetTop ?? 0) + height / 2}px`;
}

fitPageToViewport();
new ResizeObserver(fitPageToViewport).observe(pageShell);
window.addEventListener("resize", fitPageToViewport);
window.visualViewport?.addEventListener("resize", fitPageToViewport);
window.visualViewport?.addEventListener("scroll", fitPageToViewport);
document.fonts.ready.then(fitPageToViewport);
