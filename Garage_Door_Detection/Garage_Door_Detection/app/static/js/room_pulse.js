const form = document.querySelector("#pulse-config-form");
const enabledInput = document.querySelector("#pulse-enabled");
const endpointInput = document.querySelector("#pulse-endpoint-url");
const publicBaseUrlInput = document.querySelector("#pulse-public-base-url");
const intervalInput = document.querySelector("#pulse-interval");
const timeoutInput = document.querySelector("#pulse-timeout");
const tokenInput = document.querySelector("#pulse-token");
const tokenState = document.querySelector("#pulse-token-state");
const clearTokenWrap = document.querySelector("#pulse-clear-token-wrap");
const clearTokenInput = document.querySelector("#pulse-clear-token");
const sendOnChangeInput = document.querySelector("#pulse-send-on-change");
const includeImagesInput = document.querySelector("#pulse-include-images");
const statusBadge = document.querySelector("#pulse-status-badge");
const message = document.querySelector("#pulse-form-message");
const sendTestButton = document.querySelector("#pulse-send-test");
const refreshHistoryButton = document.querySelector("#pulse-refresh-history");
const historyBody = document.querySelector("#pulse-history-body");
const historySummary = document.querySelector("#pulse-history-summary");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}

function updateStatus(config) {
  const healthy = config.enabled && config.endpoint_url && !config.last_error;
  statusBadge.className = `pulse-status-badge ${healthy ? "online" : "offline"}`;
  statusBadge.innerHTML = `<span></span> ${config.enabled ? (config.last_error ? "Needs attention" : "Pulse active") : "Pulse paused"}`;
}

async function loadConfig() {
  const response = await fetch("/api/room-pulse/config");
  if (!response.ok) throw new Error("Could not load Room Pulse settings.");
  const config = await response.json();
  enabledInput.checked = config.enabled;
  endpointInput.value = config.endpoint_url || "";
  publicBaseUrlInput.value = config.public_base_url || "";
  intervalInput.value = config.interval_seconds;
  timeoutInput.value = config.timeout_seconds;
  sendOnChangeInput.checked = config.send_on_change;
  includeImagesInput.checked = config.include_image_url;
  tokenState.textContent = config.token_configured ? "saved" : "optional";
  clearTokenWrap.hidden = !config.token_configured;
  clearTokenInput.checked = false;
  updateStatus(config);
  if (config.last_error) message.textContent = `Last delivery error: ${config.last_error}`;
}

function configPayload() {
  return {
    enabled: enabledInput.checked,
    endpoint_url: endpointInput.value.trim() || null,
    public_base_url: publicBaseUrlInput.value.trim() || null,
    interval_seconds: Number(intervalInput.value),
    timeout_seconds: Number(timeoutInput.value),
    send_on_change: sendOnChangeInput.checked,
    include_image_url: includeImagesInput.checked,
    bearer_token: tokenInput.value || null,
    clear_bearer_token: clearTokenInput.checked,
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  message.textContent = "Saving pulse route...";
  try {
    const response = await fetch("/api/room-pulse/config", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configPayload()),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not save Room Pulse settings.");
    tokenInput.value = "";
    message.textContent = result.enabled ? "Pulse route saved and active." : "Pulse route saved and paused.";
    await loadConfig();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

sendTestButton.addEventListener("click", async () => {
  if (!endpointInput.value.trim()) {
    message.textContent = "Save a webhook destination before sending a test.";
    return;
  }
  if (!window.confirm("Send one test payload containing the current state of every active room?")) return;
  sendTestButton.disabled = true;
  message.textContent = "Sending test pulse...";
  try {
    const response = await fetch("/api/room-pulse/test", { method: "POST" });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Test pulse failed.");
    const delivery = result.delivery;
    message.textContent = delivery.status === "success"
      ? `Test delivered successfully with HTTP ${delivery.http_status}.`
      : `Test failed after ${delivery.attempt_count} attempts: ${delivery.error}`;
    await Promise.all([loadConfig(), loadHistory()]);
  } catch (error) {
    message.textContent = error.message;
  } finally {
    sendTestButton.disabled = false;
  }
});

async function loadHistory() {
  refreshHistoryButton.disabled = true;
  try {
    const response = await fetch("/api/room-pulse/deliveries?limit=50");
    if (!response.ok) throw new Error("Could not load pulse history.");
    const items = await response.json();
    historySummary.textContent = items.length ? `${items.length} recent deliveries.` : "No pulses sent yet.";
    historyBody.innerHTML = items.length ? items.map((item) => `
      <tr>
        <td>${escapeHtml(new Date(item.created_at).toLocaleString())}</td>
        <td>${escapeHtml(item.event_type.replaceAll("_", " "))}</td>
        <td>${item.room_count}</td>
        <td><span class="pulse-result ${escapeHtml(item.status)}">${escapeHtml(item.status)}${item.http_status ? ` · ${item.http_status}` : ""}</span>${item.error ? `<small>${escapeHtml(item.error)}</small>` : ""}</td>
        <td>${item.attempt_count}</td>
      </tr>`).join("") : '<tr><td colspan="5" class="pulse-empty">No delivery history yet.</td></tr>';
  } catch (error) {
    historySummary.textContent = error.message;
  } finally {
    refreshHistoryButton.disabled = false;
  }
}

refreshHistoryButton.addEventListener("click", loadHistory);
Promise.all([loadConfig(), loadHistory()]).catch((error) => { message.textContent = error.message; });
