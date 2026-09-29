const protectSettingsDialog = document.querySelector("#protect-settings-dialog");
const protectSettingsForm = document.querySelector("#protect-settings-form");
const openProtectSettingsButton = document.querySelector("#open-protect-settings");
const closeProtectSettingsButton = document.querySelector("#close-protect-settings");
const protectSettingsMessage = document.querySelector("#protect-settings-message");
const protectMode = document.querySelector("#protect-mode");
const protectApiKeyStatus = document.querySelector("#protect-api-key-status");
const syncUnifiButton = document.querySelector("#sync-unifi-cameras");
const captureAllButton = document.querySelector("#capture-all-cameras");
const protectMessage = document.querySelector("#protect-message");
const cameraDetailsDialog = document.querySelector("#camera-details-dialog");
const closeCameraDetailsDialogButton = document.querySelector("#close-camera-details-dialog");
const roiDialog = document.querySelector("#roi-dialog");
const closeRoiDialogButton = document.querySelector("#close-roi-dialog");
const cameraDetailsForm = document.querySelector("#camera-details-form");
const roomForm = document.querySelector("#room-form");
const cameraRows = document.querySelector("#camera-rows");
const roomRows = document.querySelector("#room-rows");
const selectedCameraIdInput = document.querySelector("#selected-camera-id");
const cameraDetailsMessage = document.querySelector("#camera-details-message");
const cameraDetailsSubtitle = document.querySelector("#camera-details-subtitle");
const cameraViewImageInput = document.querySelector("#camera-view-image");
const uploadCameraViewButton = document.querySelector("#upload-camera-view-button");
const cameraViewLink = document.querySelector("#camera-view-link");
const cameraSnapshotView = document.querySelector("#camera-snapshot-view");
const cameraSnapshotImage = document.querySelector("#camera-snapshot-image");
const cameraSnapshotLink = document.querySelector("#camera-snapshot-link");
const cameraRoiOverlay = document.querySelector("#camera-roi-overlay");
const roomMessage = document.querySelector("#room-message");
const cameraSummary = document.querySelector("#camera-summary");
const snapshotSummary = document.querySelector("#snapshot-summary");
const snapshotCameraFilter = document.querySelector("#snapshot-camera-filter");
const snapshotGallery = document.querySelector("#snapshot-gallery");
const refreshSnapshotsButton = document.querySelector("#refresh-snapshots");
const roomsTitle = document.querySelector("#rooms-title");
const roomsSummary = document.querySelector("#rooms-summary");
const addRoomButton = document.querySelector("#add-room-button");
const roiTitle = document.querySelector("#roi-title");
const roiSubtitle = document.querySelector("#roi-subtitle");
const roiMessage = document.querySelector("#roi-message");
const roiImage = document.querySelector("#roi-image");
const roiCanvas = document.querySelector("#roi-canvas");
const saveRoiButton = document.querySelector("#save-roi-button");
const roomInputs = Array.from(roomForm.querySelectorAll("input:not([type='hidden'])"));

let cameras = [];
let rooms = [];
let snapshots = [];
let selectedCameraId = null;
let roiRoom = null;
let roiDraft = null;
let roiDragStart = null;
let isDraggingRoi = false;

const CAMERA_IMAGE_WIDTH = 1920;
const CAMERA_IMAGE_HEIGHT = 1080;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return replacements[character];
  });
}

function formatDate(value) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function formatDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function emptyToNull(value) {
  return value === "" ? null : value;
}

function updateCameraInState(updatedCamera) {
  cameras = cameras.map((camera) => (camera.id === updatedCamera.id ? updatedCamera : camera));
}

function updateRoomInState(updatedRoom) {
  rooms = rooms.map((room) => (room.id === updatedRoom.id ? updatedRoom : room));
}

function roomRoiColor(room) {
  const hue = (room.id * 67 + room.room_id * 29) % 360;
  return {
    border: `hsl(${hue} 82% 52%)`,
    fill: `hsl(${hue} 82% 52% / 24%)`,
  };
}

function formatApiError(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ");
  }
  return fallback;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatApiError(error, "Request failed."));
  }
  return response.json();
}

async function uploadJson(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatApiError(error, "Upload failed."));
  }
  return response.json();
}

function selectedCamera() {
  return cameras.find((camera) => camera.id === selectedCameraId) || null;
}

function renderCameras() {
  cameraSummary.textContent =
    cameras.length === 1 ? "1 camera configured." : `${cameras.length} cameras configured.`;

  if (cameras.length === 0) {
    cameraRows.innerHTML = `<tr><td colspan="5">No cameras yet. Click Sync UniFi.</td></tr>`;
    return;
  }

  cameraRows.innerHTML = cameras
    .map(
      (camera) => `
        <tr class="${camera.id === selectedCameraId ? "selected-row" : ""}" data-select-camera="${camera.id}">
          <td>${escapeHtml(camera.name)}</td>
          <td>${escapeHtml(camera.location || "n/a")}</td>
          <td>${camera.enabled ? "Yes" : "No"}</td>
          <td>${formatDate(camera.last_snapshot_at)}</td>
          <td class="actions-cell">
            <button class="button secondary compact-button" type="button" data-capture-camera="${camera.id}">Capture</button>
            <button class="button secondary compact-button" type="button" data-edit-camera="${camera.id}">Details</button>
            <button class="button danger compact-button" type="button" data-delete-camera="${camera.id}">Delete</button>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderSnapshotFilter() {
  const selectedValue = snapshotCameraFilter.value;
  snapshotCameraFilter.innerHTML = [
    `<option value="">All cameras</option>`,
    ...cameras.map(
      (camera) => `<option value="${camera.id}">${escapeHtml(camera.name)}</option>`,
    ),
  ].join("");
  if (selectedValue && cameras.some((camera) => String(camera.id) === selectedValue)) {
    snapshotCameraFilter.value = selectedValue;
  }
}

function renderSnapshots() {
  const cameraId = snapshotCameraFilter.value ? Number(snapshotCameraFilter.value) : null;
  const visibleSnapshots = cameraId
    ? snapshots.filter((snapshot) => snapshot.camera_id === cameraId)
    : snapshots;

  snapshotSummary.textContent = cameraId
    ? `${visibleSnapshots.length} recent snapshot${visibleSnapshots.length === 1 ? "" : "s"} for this camera.`
    : `${visibleSnapshots.length} recent snapshot${visibleSnapshots.length === 1 ? "" : "s"}.`;

  if (visibleSnapshots.length === 0) {
    snapshotGallery.innerHTML = `<p class="empty-gallery">No snapshots yet. Use Capture or Capture All.</p>`;
    return;
  }

  snapshotGallery.innerHTML = visibleSnapshots
    .map((snapshot) => {
      const camera = cameras.find((item) => item.id === snapshot.camera_id);
      const cameraName = camera?.name || `Camera ${snapshot.camera_id}`;
      return `
        <article class="snapshot-card">
          <a href="${escapeHtml(snapshot.image_path)}" target="_blank" rel="noreferrer" title="Open full-size snapshot">
            <img src="${escapeHtml(snapshot.image_path)}" alt="${escapeHtml(cameraName)} snapshot" loading="lazy">
          </a>
          <div class="snapshot-card-details">
            <strong>${escapeHtml(cameraName)}</strong>
            <time datetime="${escapeHtml(snapshot.captured_at)}">${formatDate(snapshot.captured_at)}</time>
          </div>
        </article>
      `;
    })
    .join("");
}

function setRoomFormEnabled(enabled) {
  roomForm.hidden = !enabled;
  roomInputs.forEach((input) => {
    input.disabled = !enabled;
  });
  addRoomButton.disabled = !enabled;
}

function renderCameraSnapshot(camera) {
  if (!camera?.snapshot_image_path) {
    cameraSnapshotView.hidden = true;
    cameraSnapshotImage.removeAttribute("src");
    cameraSnapshotLink.href = "#";
    cameraRoiOverlay.innerHTML = "";
    return;
  }

  cameraSnapshotImage.src = camera.snapshot_image_path;
  cameraSnapshotLink.href = camera.snapshot_image_path;
  cameraSnapshotView.hidden = false;
  renderCameraRoiOverlay(camera);
}

function renderCameraRoiOverlay(camera = selectedCamera()) {
  if (!camera?.snapshot_image_path || !cameraSnapshotImage.complete) {
    cameraRoiOverlay.innerHTML = "";
    return;
  }

  const cameraRooms = rooms.filter(
    (room) => room.camera_id === camera.id && room.roi_width > 0 && room.roi_height > 0,
  );

  cameraRoiOverlay.innerHTML = cameraRooms
    .map((room) => {
      const left = (room.roi_x / CAMERA_IMAGE_WIDTH) * 100;
      const top = (room.roi_y / CAMERA_IMAGE_HEIGHT) * 100;
      const width = (room.roi_width / CAMERA_IMAGE_WIDTH) * 100;
      const height = (room.roi_height / CAMERA_IMAGE_HEIGHT) * 100;
      const color = roomRoiColor(room);
      return `
        <div
          class="camera-roi-box"
          style="
            left:${left}%;
            top:${top}%;
            width:${width}%;
            height:${height}%;
            --roi-color:${color.border};
            --roi-fill:${color.fill};
          "
          title="${escapeHtml(room.name)}"
        >
          <span>${escapeHtml(room.room_id)}</span>
        </div>
      `;
    })
    .join("");
}

function formatRoi(room) {
  if (!room.roi_width || !room.roi_height) return "Not set";
  return `${room.roi_x}, ${room.roi_y}, ${room.roi_width}x${room.roi_height}`;
}

function renderRooms() {
  const camera = selectedCamera();
  if (!camera) {
    selectedCameraIdInput.value = "";
    roomsTitle.textContent = "Rooms";
    roomsSummary.textContent = "Select a camera to see rooms.";
    roomMessage.textContent = "";
    roomRows.innerHTML = `<tr><td colspan="5">Select a camera.</td></tr>`;
    renderCameraSnapshot(null);
    setRoomFormEnabled(false);
    return;
  }

  selectedCameraIdInput.value = camera.id;
  roomsTitle.textContent = `${camera.name} Rooms`;
  setRoomFormEnabled(true);
  renderCameraSnapshot(camera);

  const cameraRooms = rooms.filter((room) => room.camera_id === camera.id);
  roomsSummary.textContent =
    cameraRooms.length === 1
      ? "1 room in this camera view."
      : `${cameraRooms.length} rooms in this camera view.`;

  if (cameraRooms.length === 0) {
    roomRows.innerHTML = `<tr><td colspan="5">No rooms for this camera yet.</td></tr>`;
    return;
  }

  roomRows.innerHTML = cameraRooms
    .map(
      (room) => `
        <tr>
          <td>${room.room_id}</td>
          <td>${escapeHtml(room.name)}</td>
          <td><span class="badge">${escapeHtml(room.current_state)}</span></td>
          <td>${formatRoi(room)}</td>
          <td class="actions-cell">
            <button class="button secondary compact-button" type="button" data-edit-roi="${room.id}" ${
              camera.snapshot_image_path ? "" : "disabled"
            }>Set ROI</button>
            <button class="button danger compact-button" type="button" data-delete-room="${room.id}">Delete</button>
          </td>
        </tr>
      `,
    )
    .join("");
}

function selectCamera(cameraId) {
  selectedCameraId = cameraId;
  renderCameras();
  renderRooms();
}

async function loadCameras() {
  cameras = await fetchJson("/api/cameras/");
  if (selectedCameraId && !cameras.some((camera) => camera.id === selectedCameraId)) {
    selectedCameraId = null;
  }
  if (!selectedCameraId && cameras.length > 0) {
    selectedCameraId = cameras[0].id;
  }
  renderCameras();
  renderSnapshotFilter();
}

async function loadRooms() {
  rooms = await fetchJson("/api/rooms/");
  renderRooms();
}

async function loadSnapshots() {
  snapshots = await fetchJson("/api/camera-snapshots/?limit=100");
  renderSnapshots();
}

async function refresh() {
  await loadCameras();
  await loadRooms();
  await loadSnapshots();
}

function openCameraDetailsDialog(camera) {
  cameraDetailsMessage.textContent = "";
  cameraDetailsSubtitle.textContent = `Camera ID ${camera.id}`;
  cameraDetailsForm.elements.id.value = camera.id;
  cameraDetailsForm.elements.name.value = camera.name || "";
  cameraDetailsForm.elements.unifi_camera_id.value = camera.unifi_camera_id || "";
  cameraDetailsForm.elements.location.value = camera.location || "";
  cameraDetailsForm.elements.enabled.checked = Boolean(camera.enabled);
  cameraDetailsForm.elements.automatic_snapshots.checked = Boolean(camera.automatic_snapshots);
  cameraDetailsForm.elements.last_snapshot_at.value = formatDateTimeLocal(camera.last_snapshot_at);
  cameraDetailsForm.elements.snapshot_image_path.value = camera.snapshot_image_path || "";
  cameraDetailsForm.elements.last_error.value = camera.last_error || "";
  cameraViewImageInput.value = "";
  if (camera.snapshot_image_path) {
    cameraViewLink.href = camera.snapshot_image_path;
    cameraViewLink.hidden = false;
  } else {
    cameraViewLink.href = "#";
    cameraViewLink.hidden = true;
  }
  if (!cameraDetailsDialog.open) {
    cameraDetailsDialog.showModal();
  }
  cameraDetailsForm.elements.name.focus();
}

function closeCameraDetailsDialog() {
  cameraDetailsDialog.close();
}

function closeRoiDialog() {
  roiDialog.close();
}

async function openProtectSettings() {
  protectSettingsMessage.textContent = "Loading settings...";
  protectSettingsDialog.showModal();
  try {
    const config = await fetchJson("/api/unifi/config");
    protectSettingsForm.elements.console_id.value = config.console_id || "";
    protectMode.textContent = config.connection_mode;
    protectApiKeyStatus.textContent = config.api_key_configured ? "Configured" : "Not configured";
    protectSettingsMessage.textContent = "";
    protectSettingsForm.elements.console_id.focus();
  } catch (error) {
    protectSettingsMessage.textContent = error.message;
  }
}

function closeProtectSettings() {
  protectSettingsDialog.close();
}

function imagePointFromEvent(event) {
  const rect = roiCanvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) * CAMERA_IMAGE_WIDTH) / rect.width;
  const y = ((event.clientY - rect.top) * CAMERA_IMAGE_HEIGHT) / rect.height;
  return {
    x: Math.round(Math.max(0, Math.min(CAMERA_IMAGE_WIDTH, x))),
    y: Math.round(Math.max(0, Math.min(CAMERA_IMAGE_HEIGHT, y))),
  };
}

function normalizeRoi(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  return {
    roi_x: x,
    roi_y: y,
    roi_width: Math.abs(end.x - start.x),
    roi_height: Math.abs(end.y - start.y),
  };
}

function drawRoi() {
  const bounds = roiImage.getBoundingClientRect();
  if (!bounds.width || !bounds.height || !roiImage.complete) return;

  roiCanvas.width = Math.round(bounds.width);
  roiCanvas.height = Math.round(bounds.height);
  const context = roiCanvas.getContext("2d");
  context.clearRect(0, 0, roiCanvas.width, roiCanvas.height);

  if (!roiDraft?.roi_width || !roiDraft?.roi_height) return;

  const scaleX = roiCanvas.width / CAMERA_IMAGE_WIDTH;
  const scaleY = roiCanvas.height / CAMERA_IMAGE_HEIGHT;
  const x = roiDraft.roi_x * scaleX;
  const y = roiDraft.roi_y * scaleY;
  const width = roiDraft.roi_width * scaleX;
  const height = roiDraft.roi_height * scaleY;

  context.fillStyle = "rgb(36 92 115 / 22%)";
  context.strokeStyle = "#f2c94c";
  context.lineWidth = 3;
  context.fillRect(x, y, width, height);
  context.strokeRect(x, y, width, height);
}

function openRoiDialog(room) {
  const camera = selectedCamera();
  if (!camera?.snapshot_image_path) {
    roomMessage.textContent = "Upload a camera view picture before setting ROI.";
    return;
  }

  roiRoom = room;
  roiDraft =
    room.roi_width && room.roi_height
      ? {
          roi_x: room.roi_x,
          roi_y: room.roi_y,
          roi_width: room.roi_width,
          roi_height: room.roi_height,
        }
      : null;
  roiMessage.textContent = "";
  roiTitle.textContent = `Set ROI: ${room.name}`;
  roiSubtitle.textContent = `${camera.name} camera view`;
  roiImage.src = camera.snapshot_image_path;
  roiDialog.showModal();
  if (roiImage.complete) {
    drawRoi();
  }
}

openProtectSettingsButton.addEventListener("click", openProtectSettings);
snapshotCameraFilter.addEventListener("change", renderSnapshots);
refreshSnapshotsButton.addEventListener("click", async () => {
  refreshSnapshotsButton.disabled = true;
  snapshotSummary.textContent = "Refreshing snapshots...";
  try {
    await loadSnapshots();
  } catch (error) {
    snapshotGallery.innerHTML = `<p class="empty-gallery">${escapeHtml(error.message)}</p>`;
  } finally {
    refreshSnapshotsButton.disabled = false;
  }
});
closeProtectSettingsButton.addEventListener("click", closeProtectSettings);
protectSettingsDialog.querySelector("[data-close-protect-settings]").addEventListener("click", closeProtectSettings);
protectSettingsDialog.addEventListener("click", (event) => {
  if (event.target === protectSettingsDialog) {
    closeProtectSettings();
  }
});
protectSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  protectSettingsMessage.textContent = "Saving settings...";
  try {
    const config = await fetchJson("/api/unifi/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ console_id: protectSettingsForm.elements.console_id.value }),
    });
    protectMode.textContent = config.connection_mode;
    protectApiKeyStatus.textContent = config.api_key_configured ? "Configured" : "Not configured";
    protectMessage.textContent = "UniFi Protect console ID saved.";
    closeProtectSettings();
  } catch (error) {
    protectSettingsMessage.textContent = error.message;
  }
});
syncUnifiButton.addEventListener("click", async () => {
  protectMessage.textContent = "Syncing cameras from UniFi Protect...";
  syncUnifiButton.disabled = true;
  try {
    const synced = await fetchJson("/api/unifi/sync", { method: "POST" });
    protectMessage.textContent = `Synced ${synced.length} UniFi camera${synced.length === 1 ? "" : "s"}.`;
    await refresh();
  } catch (error) {
    protectMessage.textContent = error.message;
  } finally {
    syncUnifiButton.disabled = false;
  }
});

captureAllButton.addEventListener("click", async () => {
  protectMessage.textContent = "Capturing all enabled UniFi cameras...";
  captureAllButton.disabled = true;
  try {
    const results = await fetchJson("/api/captures/run", { method: "POST" });
    const failures = results.filter((result) => !result.success);
    protectMessage.textContent = failures.length
      ? `Captured ${results.length - failures.length}; ${failures.length} failed.`
      : `Captured ${results.length} camera${results.length === 1 ? "" : "s"}.`;
    await refresh();
  } catch (error) {
    protectMessage.textContent = error.message;
  } finally {
    captureAllButton.disabled = false;
  }
});
closeCameraDetailsDialogButton.addEventListener("click", closeCameraDetailsDialog);
cameraDetailsDialog.addEventListener("click", (event) => {
  if (event.target === cameraDetailsDialog) {
    closeCameraDetailsDialog();
  }
});
cameraDetailsDialog
  .querySelector("[data-close-details-dialog]")
  .addEventListener("click", closeCameraDetailsDialog);
closeRoiDialogButton.addEventListener("click", closeRoiDialog);
roiDialog.querySelector("[data-close-roi-dialog]").addEventListener("click", closeRoiDialog);
roiDialog.addEventListener("click", (event) => {
  if (event.target === roiDialog) {
    closeRoiDialog();
  }
});
roiImage.addEventListener("load", drawRoi);
cameraSnapshotImage.addEventListener("load", () => renderCameraRoiOverlay());
window.addEventListener("resize", () => {
  renderCameraRoiOverlay();
  if (roiDialog.open) {
    drawRoi();
  }
});
roiCanvas.addEventListener("pointerdown", (event) => {
  if (!roiImage.complete) return;
  roiCanvas.setPointerCapture(event.pointerId);
  roiDragStart = imagePointFromEvent(event);
  roiDraft = { roi_x: roiDragStart.x, roi_y: roiDragStart.y, roi_width: 0, roi_height: 0 };
  isDraggingRoi = true;
  drawRoi();
});
roiCanvas.addEventListener("pointermove", (event) => {
  if (!isDraggingRoi || !roiDragStart) return;
  roiDraft = normalizeRoi(roiDragStart, imagePointFromEvent(event));
  drawRoi();
});
roiCanvas.addEventListener("pointerup", (event) => {
  if (!isDraggingRoi || !roiDragStart) return;
  roiDraft = normalizeRoi(roiDragStart, imagePointFromEvent(event));
  isDraggingRoi = false;
  roiDragStart = null;
  drawRoi();
});

roomForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedCameraId) return;

  roomMessage.textContent = "Adding room...";
  const formData = new FormData(roomForm);

  try {
    await fetchJson("/api/rooms/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: Number(formData.get("room_id")),
        camera_id: selectedCameraId,
        name: formData.get("name"),
      }),
    });
    roomForm.reset();
    roomMessage.textContent = "Room added.";
    await loadRooms();
  } catch (error) {
    roomMessage.textContent = error.message;
  }
});

cameraDetailsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  cameraDetailsMessage.textContent = "Saving camera...";
  const formData = new FormData(cameraDetailsForm);
  const cameraId = Number(formData.get("id"));

  try {
    const updatedCamera = await fetchJson(`/api/cameras/${cameraId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: formData.get("name"),
        location: emptyToNull(formData.get("location")),
        enabled: formData.has("enabled"),
        automatic_snapshots: formData.has("automatic_snapshots"),
        last_snapshot_at: emptyToNull(formData.get("last_snapshot_at")),
        snapshot_image_path: emptyToNull(formData.get("snapshot_image_path")),
        last_error: emptyToNull(formData.get("last_error")),
      }),
    });
    updateCameraInState(updatedCamera);
    selectedCameraId = updatedCamera.id;
    closeCameraDetailsDialog();
    await refresh();
  } catch (error) {
    cameraDetailsMessage.textContent = error.message;
  }
});

uploadCameraViewButton.addEventListener("click", async () => {
  const cameraId = Number(cameraDetailsForm.elements.id.value);
  const file = cameraViewImageInput.files[0];
  if (!cameraId || !file) {
    cameraDetailsMessage.textContent = "Choose an image first.";
    return;
  }

  cameraDetailsMessage.textContent = "Uploading picture...";
  const formData = new FormData();
  formData.append("image", file);

  try {
    const updatedCamera = await uploadJson(`/api/cameras/${cameraId}/snapshot-image`, formData);
    updateCameraInState(updatedCamera);
    selectedCameraId = updatedCamera.id;
    openCameraDetailsDialog(updatedCamera);
    cameraDetailsMessage.textContent = "Picture uploaded.";
    renderCameras();
    renderRooms();
    await loadSnapshots();
  } catch (error) {
    cameraDetailsMessage.textContent = error.message;
  }
});

saveRoiButton.addEventListener("click", async () => {
  if (!roiRoom || !roiDraft?.roi_width || !roiDraft?.roi_height) {
    roiMessage.textContent = "Drag a box around the garage door first.";
    return;
  }

  roiMessage.textContent = "Saving ROI...";
  try {
    const updatedRoom = await fetchJson(`/api/rooms/${roiRoom.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(roiDraft),
    });
    updateRoomInState(updatedRoom);
    closeRoiDialog();
    renderRooms();
    renderCameraRoiOverlay();
  } catch (error) {
    roiMessage.textContent = error.message;
  }
});

cameraRows.addEventListener("click", async (event) => {
  const captureButton = event.target.closest("[data-capture-camera]");
  if (captureButton) {
    const cameraId = Number(captureButton.dataset.captureCamera);
    protectMessage.textContent = "Capturing camera...";
    captureButton.disabled = true;
    try {
      const result = await fetchJson(`/api/cameras/${cameraId}/capture`, { method: "POST" });
      protectMessage.textContent = result.success
        ? `Captured ${result.camera_name}.`
        : `Capture failed: ${result.error}`;
      await refresh();
    } catch (error) {
      protectMessage.textContent = error.message;
    } finally {
      captureButton.disabled = false;
    }
    return;
  }

  const editButton = event.target.closest("[data-edit-camera]");
  if (editButton) {
    const camera = cameras.find((item) => item.id === Number(editButton.dataset.editCamera));
    if (camera) {
      openCameraDetailsDialog(camera);
    }
    return;
  }

  const deleteButton = event.target.closest("[data-delete-camera]");
  if (deleteButton) {
    if (!confirm("Delete this camera and its rooms?")) return;
    await fetchJson(`/api/cameras/${deleteButton.dataset.deleteCamera}`, { method: "DELETE" });
    await refresh();
    return;
  }

  const row = event.target.closest("[data-select-camera]");
  if (!row) return;
  selectCamera(Number(row.dataset.selectCamera));
});

roomRows.addEventListener("click", async (event) => {
  const roiButton = event.target.closest("[data-edit-roi]");
  if (roiButton) {
    const room = rooms.find((item) => item.id === Number(roiButton.dataset.editRoi));
    if (room) {
      openRoiDialog(room);
    }
    return;
  }

  const button = event.target.closest("[data-delete-room]");
  if (!button || !confirm("Delete this room?")) return;
  await fetchJson(`/api/rooms/${button.dataset.deleteRoom}`, { method: "DELETE" });
  await loadRooms();
});

refresh().catch((error) => {
  cameraRows.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
  roomRows.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
  snapshotGallery.innerHTML = `<p class="empty-gallery">${escapeHtml(error.message)}</p>`;
});
