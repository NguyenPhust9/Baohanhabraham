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
  model: "Vui lòng nhập mẫu xe đạp.",
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

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const requiredFields = [...form.querySelectorAll("[required]")];
  const valid = requiredFields.map(validateField).every(Boolean);

  if (!valid) {
    requiredFields.find((field) => field.getAttribute("aria-invalid") === "true")?.focus();
    return;
  }

  toast.classList.add("show");
  form.reset();
  setTimeout(() => toast.classList.remove("show"), 5000);
});

closeToast.addEventListener("click", () => toast.classList.remove("show"));
