const $ = (selector) => document.querySelector(selector);

async function api(path, data = {}) {
  const response = await fetch(path, {
    method: path === "/api/status" ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: path === "/api/status" ? undefined : JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

async function refreshStatus() {
  const status = await api("/api/status");
  $("#memberCount").textContent = status.members.toLocaleString("ko-KR");
  if (status.user) {
    $("#loginOpen").textContent = `${status.user.name}님 · 로그아웃`;
    $("#loginOpen").dataset.loggedIn = "true";
  }
}

function showMessage(element, text, success = false) {
  element.textContent = text;
  element.classList.toggle("success", success);
}

$("#joinForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const result = await api("/api/register", values);
    showMessage($("#formMessage"), result.message, true);
    event.currentTarget.reset();
    await refreshStatus();
  } catch (error) { showMessage($("#formMessage"), error.message); }
});

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await api("/api/login", Object.fromEntries(new FormData(event.currentTarget)));
    showMessage($("#loginMessage"), result.message, true);
    await refreshStatus();
    setTimeout(() => $("#loginModal").close(), 600);
  } catch (error) { showMessage($("#loginMessage"), error.message); }
});

$("#loginOpen").addEventListener("click", async () => {
  if ($("#loginOpen").dataset.loggedIn) {
    await api("/api/logout");
    location.reload();
  } else $("#loginModal").showModal();
});
$("#loginClose").addEventListener("click", () => $("#loginModal").close());
refreshStatus().catch(console.error);
