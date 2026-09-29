const roomRows = document.querySelector("#dashboard-room-rows");
const roomSummary = document.querySelector("#dashboard-room-summary");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeState(value) {
  const state = String(value ?? "unknown").toLowerCase();
  return ["open", "closed"].includes(state) ? state : "unknown";
}

function stateLabel(state) {
  return state.charAt(0).toUpperCase() + state.slice(1);
}

function cropImage(room) {
  if (!room.latest_crop_image_path) {
    return '<div class="room-crop-placeholder">No image</div>';
  }
  const imagePath = escapeHtml(room.latest_crop_image_path);
  const roomNumber = escapeHtml(room.room_number);
  return `
    <a class="room-crop-link" href="${imagePath}" target="_blank" rel="noreferrer">
      <img class="room-crop-image" src="${imagePath}" alt="Most recent crop for room ${roomNumber}" loading="lazy">
    </a>
  `;
}

function renderRooms(rooms) {
  if (!rooms.length) {
    roomRows.innerHTML = '<p class="room-status-empty">No rooms are configured.</p>';
    roomSummary.textContent = "No rooms are configured.";
    return;
  }

  const counts = { open: 0, closed: 0, unknown: 0 };
  roomRows.innerHTML = rooms.map((room) => {
    const state = normalizeState(room.current_state);
    counts[state] += 1;
    return `
      <article class="room-status-card room-status-card-${state}">
        ${cropImage(room)}
        <div class="room-status-details">
          <strong class="room-status-number">Room ${escapeHtml(room.room_number)}</strong>
          <span class="room-state room-state-${state}">${stateLabel(state)}</span>
        </div>
      </article>
    `;
  }).join("");

  roomSummary.textContent = `${rooms.length} rooms · ${counts.open} open · ${counts.closed} closed · ${counts.unknown} unknown`;
}

async function loadRooms() {
  try {
    const response = await fetch("/api/dashboard/rooms");
    if (!response.ok) {
      throw new Error(`Request failed with HTTP ${response.status}`);
    }
    renderRooms(await response.json());
  } catch (error) {
    roomRows.innerHTML = '<p class="room-status-empty">Unable to load rooms.</p>';
    roomSummary.textContent = error.message;
  }
}

loadRooms();
window.setInterval(loadRooms, 15_000);
