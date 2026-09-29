const generateCropsButton = document.querySelector("#generate-training-crops");
const cropGenerationMessage = document.querySelector("#crop-generation-message");
const cropGenerationLog = document.querySelector("#crop-generation-log");
const cropGenerationLogCount = document.querySelector("#crop-generation-log-count");
const cropGenerationLogOutput = document.querySelector("#crop-generation-log-output");
const unlabeledCropSummary = document.querySelector("#unlabeled-crop-summary");
const unlabeledCropEmpty = document.querySelector("#unlabeled-crop-empty");
const unlabeledCropList = document.querySelector("#unlabeled-crop-list");
const labelingWorkspace = document.querySelector("#labeling-workspace");
const activeCropImage = document.querySelector("#active-crop-image");
const activeCropRoom = document.querySelector("#active-crop-room");
const activeCropCamera = document.querySelector("#active-crop-camera");
const activeCropTime = document.querySelector("#active-crop-time");
const activeCropPreliminary = document.querySelector("#active-crop-preliminary");
const activeCropLabels = document.querySelector("#active-crop-labels");
const labelingMessage = document.querySelector("#labeling-message");
const refreshUnlabeledCropsButton = document.querySelector("#refresh-unlabeled-crops");
const loadMoreCropsButton = document.querySelector("#load-more-crops");
const skipCropButton = document.querySelector("#skip-crop");
const confirmPreliminaryButton = document.querySelector("#confirm-preliminary-label");
const confirmPreliminaryText = document.querySelector("#confirm-preliminary-text");
const undoCropLabelButton = document.querySelector("#undo-crop-label");
const labelButtons = Array.from(document.querySelectorAll("[data-crop-label]"));
const runLabelButtons = Array.from(document.querySelectorAll("[data-crop-run-label]"));
const vehicleLabelButtons = Array.from(document.querySelectorAll("[data-vehicle-label]"));
const vehicleRunLabelButtons = Array.from(document.querySelectorAll("[data-vehicle-run-label]"));
const exportDatasetButton = document.querySelector("#export-training-dataset");
const downloadDatasetLink = document.querySelector("#download-training-dataset");
const datasetExportMessage = document.querySelector("#dataset-export-message");
const exportMode = document.querySelector("#export-mode");
const exportCapturedFrom = document.querySelector("#export-captured-from");
const exportCapturedThrough = document.querySelector("#export-captured-through");
const exportLowConfidence = document.querySelector("#export-low-confidence");
const exportProbabilityMargin = document.querySelector("#export-probability-margin");
const exportRandomPercent = document.querySelector("#export-random-percent");
const exportDuplicateWindow = document.querySelector("#export-duplicate-window");
const exportPerceptualDistance = document.querySelector("#export-perceptual-distance");
const exportValidationPercent = document.querySelector("#export-validation-percent");
const exportTestPercent = document.querySelector("#export-test-percent");
const exportMinimumClassPercent = document.querySelector("#export-minimum-class-percent");
const exportMinimumClassValue = document.querySelector("#export-minimum-class-value");
const exportVehicleMinimumClassPercent = document.querySelector("#export-vehicle-minimum-class-percent");
const exportVehicleMinimumClassValue = document.querySelector("#export-vehicle-minimum-class-value");
const exportIncludeLowConfidence = document.querySelector("#export-include-low-confidence");
const exportIncludeMisclassified = document.querySelector("#export-include-misclassified");
const exportIncludeEdgeCases = document.querySelector("#export-include-edge-cases");
const refreshDatasetPreviewButton = document.querySelector("#refresh-dataset-preview");
const datasetPreviewMessage = document.querySelector("#dataset-preview-message");
const datasetPreviewTaskCounts = document.querySelector("#dataset-preview-task-counts");
const datasetHelpDialog = document.querySelector("#dataset-help-dialog");
const datasetHelpTitle = document.querySelector("#dataset-help-title");
const datasetHelpText = document.querySelector("#dataset-help-text");
const datasetHelpButtons = Array.from(document.querySelectorAll("[data-dataset-help]"));
const unlabeledRoomFilter = document.querySelector("#unlabeled-room-filter");
const unlabeledStatusFilter = document.querySelector("#unlabeled-status-filter");
const doorLabelFilter = document.querySelector("#door-label-filter");
const vehicleLabelFilter = document.querySelector("#vehicle-label-filter");
const labelProgressTotal = document.querySelector("#label-progress-total");
const labelProgressDoor = document.querySelector("#label-progress-door");
const labelProgressVehicle = document.querySelector("#label-progress-vehicle");
const labelProgressComplete = document.querySelector("#label-progress-complete");
const labelProgressReview = document.querySelector("#label-progress-review");
const batchConfidenceThreshold = document.querySelector("#batch-confidence-threshold");
const batchConfidenceValue = document.querySelector("#batch-confidence-value");
const batchRoomFilter = document.querySelector("#batch-room-filter");
const batchEligibleCount = document.querySelector("#batch-eligible-count");
const batchOpenCount = document.querySelector("#batch-open-count");
const batchClosedCount = document.querySelector("#batch-closed-count");
const batchRemainingCount = document.querySelector("#batch-remaining-count");
const approveLabelBatchButton = document.querySelector("#approve-label-batch");
const undoLabelBatchButton = document.querySelector("#undo-label-batch");
const batchApprovalMessage = document.querySelector("#batch-approval-message");
const batchApprovalDialog = document.querySelector("#batch-approval-dialog");
const batchConfirmationSummary = document.querySelector("#batch-confirmation-summary");
const confirmLabelBatchButton = document.querySelector("#confirm-label-batch");

const cropPageSize = 48;
let unlabeledCrops = [];
let unlabeledCropTotal = 0;
let selectedCropIndex = 0;
let labelRequestInProgress = false;
const labelHistory = [];
let unlabeledRoomOptions = [];
let batchPreview = null;
let batchRequestInProgress = false;
let batchPreviewTimer = null;

const allLabelButtons = [
  ...labelButtons,
  ...runLabelButtons,
  ...vehicleLabelButtons,
  ...vehicleRunLabelButtons,
];

function displayLabel(value) {
  if (!value) return "Missing";
  return value.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

const datasetHelpContent = {
  "export-mode": {
    title: "Export mode",
    text: "Door creates a Closed/Partial/Open image-folder dataset. Vehicle creates a Present/Absent dataset. Both Separate puts both conventional datasets in one ZIP with shared splits. Multi-task writes each image once with door_label_valid and vehicle_label_valid flags so a two-head trainer can mask unavailable targets.",
  },
  "captured-from": {
    title: "Captured from",
    text: "Includes reviewed images captured on or after this date, using UTC capture timestamps. Leave it blank for no lower date limit. Moving it later excludes older images before duplicate filtering, sampling, balancing, and split assignment.",
  },
  "captured-through": {
    title: "Captured through",
    text: "Includes reviewed images through the end of this date, using UTC capture timestamps. Leave it blank for no upper date limit. Moving it earlier excludes newer images before curation. Only fixed benchmark images inside the range appear in the test folder; the saved benchmark definition is not changed.",
  },
  "low-confidence": {
    title: "Low-confidence cutoff",
    text: "Prioritizes reviewed images whose latest model confidence is below this percentage. Raising the cutoff includes more predictions as uncertain and usually makes the export larger. Lowering it focuses on only the least-confident predictions. This setting never changes the human-confirmed label.",
  },
  "probability-margin": {
    title: "Small probability margin",
    text: "Measures the difference between the model's Open and Closed probabilities. Images below this margin are treated as ambiguous and prioritized. Raising the value includes more borderline predictions; lowering it selects only very close decisions.",
  },
  "routine-sample": {
    title: "Routine sample",
    text: "Keeps this deterministic percentage of reviewed images that are not low-confidence, corrected mistakes, edge cases, or benchmark images. Raising it produces a larger and more production-representative dataset but may add repetition. Lowering it creates a smaller dataset concentrated on difficult cases.",
  },
  "duplicate-window": {
    title: "Duplicate window",
    text: "Compares perceptual hashes for images from the same camera, door, and reviewed label within this many minutes. Raising it removes similar scenes across a longer period. Lowering it keeps more time-separated images. Set it to 0 to disable visual time-window filtering; exact byte duplicates are still removed.",
  },
  "visual-distance": {
    title: "Visual match distance",
    text: "Sets the maximum 64-bit perceptual-hash difference considered visually duplicate. Lower values require closer matches and keep more images. Higher values remove more variation and can accidentally treat meaningfully different scenes as duplicates. The default of 6 is moderately conservative.",
  },
  "validation-split": {
    title: "Validation split",
    text: "Assigns approximately this percentage of the balanced non-test pool to validation. Whole camera-and-hour groups stay together to prevent leakage, so the final percentage and class ratio can vary slightly. Raising it improves validation coverage but leaves fewer training images.",
  },
  "test-split": {
    title: "Initial fixed test split",
    text: "Used only when the fixed benchmark is created for the first time. Raising it reserves more reviewed images for objective testing and leaves fewer for training. After the benchmark exists, changing this value has no effect because test membership remains frozen across model versions.",
  },
  "class-balance": {
    title: "Door minimum-to-largest ratio",
    text: "Balances Open, Closed, and Partial independently after curation. At 40%, no available door class may have more than 2.5 times as many new training/validation targets as the smallest available class. Classes with no reviewed images are ignored until examples exist. Set it to 0% to disable door balancing. The fixed test benchmark is never changed.",
  },
  "vehicle-class-balance": {
    title: "Vehicle minimum-to-largest ratio",
    text: "Balances verified Present and Absent targets independently from door state. At 40%, the larger class is limited to 2.5 times the smaller class in new training/validation targets. Not Observable and Unsure are not treated as vehicle classes. Set it to 0% to disable vehicle balancing.",
  },
  "include-low-confidence": {
    title: "Always include low-confidence predictions",
    text: "When enabled, reviewed images meeting either uncertainty threshold are kept after duplicate filtering. Disable it to stop uncertainty alone from guaranteeing inclusion. Those images may still be exported as corrected mistakes, edge cases, routine samples, representative floors, or fixed benchmark images.",
  },
  "include-misclassified": {
    title: "Always include corrected misclassifications",
    text: "Prioritizes images where the latest Open or Closed model prediction disagrees with the operator-confirmed label. These are especially valuable for correcting known model weaknesses. Disabling it means a corrected mistake must qualify through another category or routine sampling to be exported.",
  },
  "include-edge-cases": {
    title: "Always include visual edge cases",
    text: "Uses OpenCV heuristics to prioritize dark images, strong glare, and possible blur. Disable it to stop those visual signals alone from guaranteeing inclusion. It does not currently identify rain, obstruction, partial openings, dirty lenses, or camera movement, and edge-case images may still qualify through another category.",
  },
};

datasetHelpButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const help = datasetHelpContent[button.dataset.datasetHelp];
    if (!help) return;
    datasetHelpTitle.textContent = help.title;
    datasetHelpText.textContent = help.text;
    datasetHelpDialog.showModal();
  });
});

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
  return new Date(value).toLocaleString();
}

function cropSummary(result) {
  return [
    `Processed ${result.snapshots_considered} snapshot${result.snapshots_considered === 1 ? "" : "s"}.`,
    `Created ${result.crops_created}, updated ${result.crops_updated}, skipped ${result.crops_skipped}.`,
    `Missing sources ${result.missing_sources}, failed ${result.failed_sources}.`,
  ].join(" ");
}

generateCropsButton.addEventListener("click", async () => {
  generateCropsButton.disabled = true;
  cropGenerationMessage.textContent = "Generating crop images. This may take a moment...";
  cropGenerationLog.open = false;
  cropGenerationLogCount.textContent = "Running...";
  cropGenerationLogOutput.textContent = "Waiting for crop generation results...";

  try {
    const response = await fetch("/api/training/crops/generate", { method: "POST" });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || "Crop generation failed.");
    }
    const result = await response.json();
    cropGenerationMessage.textContent = cropSummary(result);
    cropGenerationLogCount.textContent = `${result.log_entries.length} entries`;
    cropGenerationLogOutput.textContent = result.log_entries.length
      ? result.log_entries.join("\n")
      : "No matching snapshot images were found.";
    await loadTrainingQueue();
  } catch (error) {
    cropGenerationMessage.textContent = error.message;
    cropGenerationLogCount.textContent = "Failed";
    cropGenerationLogOutput.textContent = `FAILED    ${error.message}`;
  } finally {
    generateCropsButton.disabled = false;
  }
});

function selectedCrop() {
  return unlabeledCrops[selectedCropIndex] || null;
}

function confirmablePreliminaryLabel(crop) {
  return ["open", "closed"].includes(crop?.preliminary_label)
    ? crop.preliminary_label
    : null;
}

function renderPreliminarySuggestion(crop) {
  if (!crop) {
    activeCropPreliminary.className = "preliminary-suggestion";
    activeCropPreliminary.textContent = "No crop selected.";
    confirmPreliminaryText.textContent = "Confirm Preliminary";
    confirmPreliminaryButton.disabled = true;
    return;
  }
  const label = crop?.preliminary_label || null;
  const confidence = crop?.preliminary_confidence;
  const confidenceText = Number.isFinite(confidence)
    ? ` (${(confidence * 100).toFixed(1)}%)`
    : "";
  activeCropPreliminary.className = "preliminary-suggestion";

  if (!label) {
    activeCropPreliminary.textContent = "Preliminary model is processing...";
    confirmPreliminaryText.textContent = "Confirm Preliminary";
  } else if (label === "unknown") {
    activeCropPreliminary.textContent = `Preliminary: Unsure${confidenceText} — choose a label`;
    activeCropPreliminary.classList.add("preliminary-unknown");
    confirmPreliminaryText.textContent = "No Label to Confirm";
  } else {
    const displayLabel = label.charAt(0).toUpperCase() + label.slice(1);
    activeCropPreliminary.textContent = `Preliminary: ${displayLabel}${confidenceText}`;
    activeCropPreliminary.classList.add(`preliminary-${label}`);
    confirmPreliminaryText.textContent = `Confirm ${displayLabel}`;
  }
  confirmPreliminaryButton.disabled =
    labelRequestInProgress || !confirmablePreliminaryLabel(crop);
}

function renderUnlabeledCrops() {
  const roomDescription = unlabeledRoomFilter.value
    ? ` for Room ${unlabeledRoomFilter.value}`
    : " across all rooms";
  const statusDescription = unlabeledStatusFilter.value
    ? ` with preliminary ${unlabeledStatusFilter.value}`
    : "";
  const doorDescription = doorLabelFilter.value
    ? `, door ${displayLabel(doorLabelFilter.value).toLowerCase()}`
    : "";
  const vehicleDescription = vehicleLabelFilter.value
    ? `, vehicle ${displayLabel(vehicleLabelFilter.value).toLowerCase()}`
    : "";
  unlabeledCropSummary.textContent = `${unlabeledCropTotal} matching crop${unlabeledCropTotal === 1 ? "" : "s"}${statusDescription}${doorDescription}${vehicleDescription}${roomDescription}. Showing ${unlabeledCrops.length}.`;
  const crop = selectedCrop();
  const hasCrops = Boolean(crop);
  labelingWorkspace.hidden = !hasCrops;
  unlabeledCropEmpty.hidden = hasCrops || unlabeledCropTotal > 0;
  unlabeledCropEmpty.textContent = "No unlabeled crops remain.";

  if (!hasCrops) {
    activeCropImage.removeAttribute("src");
    renderPreliminarySuggestion(null);
    unlabeledCropList.innerHTML = "";
    loadMoreCropsButton.hidden = true;
    return;
  }

  activeCropImage.src = crop.image_path;
  activeCropImage.alt = `${crop.room_name} crop awaiting a label`;
  activeCropRoom.textContent = `${crop.room_name} (Room ${crop.room_number})`;
  activeCropCamera.textContent = crop.camera_name;
  activeCropTime.textContent = formatDate(crop.captured_at);
  activeCropTime.dateTime = crop.captured_at;
  activeCropLabels.textContent = `Door: ${displayLabel(crop.door_label)} · Vehicle: ${displayLabel(crop.vehicle_label)}`;
  renderPreliminarySuggestion(crop);

  unlabeledCropList.innerHTML = unlabeledCrops
    .map(
      (item, index) => `
        <button
          class="crop-thumbnail${index === selectedCropIndex ? " selected" : ""}"
          type="button"
          data-select-crop="${item.id}"
          aria-label="Select ${escapeHtml(item.room_name)} crop from ${escapeHtml(formatDate(item.captured_at))}"
          aria-pressed="${index === selectedCropIndex}"
        >
          <img src="${escapeHtml(item.image_path)}" alt="" loading="lazy">
          <span>${escapeHtml(item.room_name)}</span>
        </button>
      `,
    )
    .join("");
  loadMoreCropsButton.hidden = unlabeledCrops.length >= unlabeledCropTotal;
}

async function loadUnlabeledCrops({ append = false } = {}) {
  const offset = append ? unlabeledCrops.length : 0;
  const previouslySelectedCropId = selectedCrop()?.id;
  refreshUnlabeledCropsButton.disabled = true;
  loadMoreCropsButton.disabled = true;
  unlabeledCropSummary.textContent = append ? "Loading more crops..." : "Loading unlabeled crops...";
  try {
    const params = new URLSearchParams({ limit: cropPageSize, offset });
    if (unlabeledRoomFilter.value) params.set("room_number", unlabeledRoomFilter.value);
    if (unlabeledStatusFilter.value) {
      params.set("preliminary_label", unlabeledStatusFilter.value);
    }
    if (doorLabelFilter.value) params.set("door_label", doorLabelFilter.value);
    if (vehicleLabelFilter.value) params.set("vehicle_label", vehicleLabelFilter.value);
    const response = await fetch(`/api/training/crops/unlabeled?${params}`);
    if (!response.ok) throw new Error("Could not load unlabeled crops.");
    const result = await response.json();
    unlabeledCrops = append ? [...unlabeledCrops, ...result.items] : result.items;
    unlabeledCropTotal = result.total;
    if (!append) {
      const previousIndex = unlabeledCrops.findIndex(
        (crop) => crop.id === previouslySelectedCropId,
      );
      selectedCropIndex = Math.max(0, previousIndex);
    }
    renderUnlabeledCrops();
  } catch (error) {
    unlabeledCropSummary.textContent = error.message;
  } finally {
    refreshUnlabeledCropsButton.disabled = false;
    loadMoreCropsButton.disabled = false;
  }
}

function renderRoomOptions() {
  const selected = unlabeledRoomFilter.value;
  const batchSelected = batchRoomFilter.value;
  const total = unlabeledRoomOptions.reduce((sum, option) => sum + option.count, 0);
  unlabeledRoomFilter.innerHTML = [
    `<option value="">All rooms (${total})</option>`,
    ...unlabeledRoomOptions.map(
      (option) =>
        `<option value="${option.room_number}">Room ${option.room_number} — ${escapeHtml(option.room_name)} (${option.count})</option>`,
    ),
  ].join("");
  if (selected && unlabeledRoomOptions.some((option) => String(option.room_number) === selected)) {
    unlabeledRoomFilter.value = selected;
  }
  batchRoomFilter.innerHTML = [
    `<option value="">All rooms (${total})</option>`,
    ...unlabeledRoomOptions.map(
      (option) =>
        `<option value="${option.room_number}">Room ${option.room_number} — ${escapeHtml(option.room_name)} (${option.count})</option>`,
    ),
  ].join("");
  if (batchSelected && unlabeledRoomOptions.some((option) => String(option.room_number) === batchSelected)) {
    batchRoomFilter.value = batchSelected;
  }
}

function batchPayload() {
  return {
    confidence_threshold: Number(batchConfidenceThreshold.value) / 100,
    room_number: batchRoomFilter.value ? Number(batchRoomFilter.value) : null,
  };
}

function renderBatchPreview(preview) {
  batchPreview = preview;
  batchEligibleCount.textContent = preview.eligible.toLocaleString();
  batchOpenCount.textContent = preview.predicted_open.toLocaleString();
  batchClosedCount.textContent = preview.predicted_closed.toLocaleString();
  batchRemainingCount.textContent = preview.remaining_manual.toLocaleString();
  approveLabelBatchButton.disabled = batchRequestInProgress || preview.eligible === 0;
  undoLabelBatchButton.disabled = batchRequestInProgress || !preview.can_undo;
  const roomText = preview.room_number === null ? "all rooms" : `Room ${preview.room_number}`;
  batchApprovalMessage.textContent = `${preview.eligible.toLocaleString()} of ${preview.total_unlabeled.toLocaleString()} unlabeled images in ${roomText} meet the threshold.`;
  if (preview.can_undo) {
    undoLabelBatchButton.textContent = `Undo Latest Batch (${preview.latest_batch_count.toLocaleString()})`;
  } else {
    undoLabelBatchButton.textContent = "Undo Latest Batch";
  }
}

async function refreshBatchPreview() {
  batchConfidenceValue.textContent = `${Number(batchConfidenceThreshold.value).toFixed(1)}%`;
  approveLabelBatchButton.disabled = true;
  try {
    const response = await fetch("/api/training/labels/batches/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batchPayload()),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not load the batch preview.");
    renderBatchPreview(result);
  } catch (error) {
    batchPreview = null;
    batchApprovalMessage.textContent = error.message;
    approveLabelBatchButton.disabled = true;
  }
}

function scheduleBatchPreview() {
  batchConfidenceValue.textContent = `${Number(batchConfidenceThreshold.value).toFixed(1)}%`;
  batchPreview = null;
  approveLabelBatchButton.disabled = true;
  window.clearTimeout(batchPreviewTimer);
  batchPreviewTimer = window.setTimeout(refreshBatchPreview, 200);
}

async function loadRoomOptions() {
  const response = await fetch("/api/training/crops/unlabeled/rooms");
  if (!response.ok) throw new Error("Could not load room filters.");
  unlabeledRoomOptions = await response.json();
  renderRoomOptions();
}

async function loadLabelProgress() {
  const response = await fetch("/api/training/crops/label-progress");
  if (!response.ok) throw new Error("Could not load labeling progress.");
  const progress = await response.json();
  labelProgressTotal.textContent = progress.total.toLocaleString();
  labelProgressDoor.textContent = progress.door_labeled.toLocaleString();
  labelProgressVehicle.textContent = progress.vehicle_labeled.toLocaleString();
  labelProgressComplete.textContent = progress.fully_labeled.toLocaleString();
  labelProgressReview.textContent = progress.needs_review.toLocaleString();
}

async function loadTrainingQueue() {
  try {
    await Promise.all([loadRoomOptions(), loadLabelProgress()]);
    await Promise.all([loadUnlabeledCrops(), refreshBatchPreview()]);
  } catch (error) {
    unlabeledCropSummary.textContent = error.message;
  }
}

approveLabelBatchButton.addEventListener("click", () => {
  if (!batchPreview?.eligible || batchRequestInProgress) return;
  const roomText = batchPreview.room_number === null
    ? "all rooms"
    : `Room ${batchPreview.room_number}`;
  batchConfirmationSummary.textContent = `Approve ${batchPreview.eligible.toLocaleString()} images (${batchPreview.predicted_open.toLocaleString()} Open and ${batchPreview.predicted_closed.toLocaleString()} Closed) in ${roomText} at ${Number(batchConfidenceThreshold.value).toFixed(1)}% confidence or higher?`;
  batchApprovalDialog.showModal();
});

batchApprovalDialog.addEventListener("close", async () => {
  if (batchApprovalDialog.returnValue !== "default" || batchRequestInProgress) return;
  batchRequestInProgress = true;
  approveLabelBatchButton.disabled = true;
  undoLabelBatchButton.disabled = true;
  confirmLabelBatchButton.disabled = true;
  batchApprovalMessage.textContent = "Approving matching labels...";
  try {
    const response = await fetch("/api/training/labels/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batchPayload()),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not approve the label batch.");
    batchApprovalMessage.textContent = `Batch ${result.batch_id} approved ${result.images_approved.toLocaleString()} images.`;
    await loadTrainingQueue();
  } catch (error) {
    batchApprovalMessage.textContent = error.message;
  } finally {
    batchRequestInProgress = false;
    confirmLabelBatchButton.disabled = false;
    await refreshBatchPreview();
  }
});

undoLabelBatchButton.addEventListener("click", async () => {
  if (batchRequestInProgress || !batchPreview?.can_undo) return;
  if (!window.confirm(`Undo the latest batch and return up to ${batchPreview.latest_batch_count.toLocaleString()} images to manual review?`)) return;
  batchRequestInProgress = true;
  approveLabelBatchButton.disabled = true;
  undoLabelBatchButton.disabled = true;
  batchApprovalMessage.textContent = "Undoing the latest batch...";
  try {
    const response = await fetch("/api/training/labels/batches/latest", { method: "DELETE" });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not undo the latest batch.");
    batchApprovalMessage.textContent = `Batch ${result.batch_id} undone; ${result.labels_reverted.toLocaleString()} images returned to review.`;
    await loadTrainingQueue();
  } catch (error) {
    batchApprovalMessage.textContent = error.message;
  } finally {
    batchRequestInProgress = false;
    await refreshBatchPreview();
  }
});

batchConfidenceThreshold.addEventListener("input", scheduleBatchPreview);
batchRoomFilter.addEventListener("change", refreshBatchPreview);

function skipSelectedCrop() {
  if (unlabeledCrops.length < 2 || labelRequestInProgress) return;
  selectedCropIndex = (selectedCropIndex + 1) % unlabeledCrops.length;
  labelingMessage.textContent = "Skipped without labeling.";
  renderUnlabeledCrops();
}

async function labelSelectedCrop(label, dimension = "door", confirmedPreliminary = false) {
  const crop = selectedCrop();
  if (!crop || labelRequestInProgress) return;
  labelRequestInProgress = true;
  allLabelButtons.forEach((button) => { button.disabled = true; });
  skipCropButton.disabled = true;
  confirmPreliminaryButton.disabled = true;
  undoCropLabelButton.disabled = true;
  labelingMessage.textContent = confirmedPreliminary
    ? `Confirming preliminary ${label} door label...`
    : `Saving ${displayLabel(label)} ${dimension} label...`;

  try {
    const response = await fetch(`/api/training/crops/${crop.id}/label`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dimension === "vehicle" ? { vehicle_label: label } : { label }),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not save the crop label.");
    labelHistory.push({ cropIds: [crop.id], dimension });
    undoCropLabelButton.disabled = false;
    if (dimension === "door" && label === "closed") {
      labelingMessage.textContent = confirmedPreliminary
        ? "Confirmed Closed; vehicle visibility set to Not Observable."
        : "Saved Closed; vehicle visibility set to Not Observable.";
    } else {
      labelingMessage.textContent = confirmedPreliminary
        ? `Confirmed preliminary ${label} door label.`
        : `Saved ${displayLabel(label)} as the ${dimension} label.`;
    }
    await loadTrainingQueue();
  } catch (error) {
    labelingMessage.textContent = error.message;
  } finally {
    labelRequestInProgress = false;
    allLabelButtons.forEach((button) => { button.disabled = false; });
    skipCropButton.disabled = false;
    undoCropLabelButton.disabled = labelHistory.length === 0;
    renderPreliminarySuggestion(selectedCrop());
  }
}

async function labelSelectedCropRun(label, dimension = "door") {
  const crop = selectedCrop();
  if (!crop || labelRequestInProgress) return;
  labelRequestInProgress = true;
  allLabelButtons.forEach((button) => { button.disabled = true; });
  skipCropButton.disabled = true;
  confirmPreliminaryButton.disabled = true;
  undoCropLabelButton.disabled = true;
  labelingMessage.textContent = `Labeling up to eight consecutive Room ${crop.room_number} images ${displayLabel(label)} for ${dimension}...`;

  try {
    const response = await fetch("/api/training/crops/label-run", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_crop_id: crop.id,
        ...(dimension === "vehicle" ? { vehicle_label: label } : { label }),
        count: 8,
        preliminary_label: dimension === "door" ? (unlabeledStatusFilter.value || null) : null,
      }),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not label the image run.");
    labelHistory.push({ cropIds: result.crop_ids, dimension });
    const derivedVehicleText = dimension === "door" && label === "closed"
      ? " Vehicle visibility was set to Not Observable."
      : "";
    labelingMessage.textContent = `Labeled ${result.count} consecutive Room ${crop.room_number} image${result.count === 1 ? "" : "s"} ${displayLabel(label)} for ${dimension}.${derivedVehicleText}`;
    await loadTrainingQueue();
  } catch (error) {
    labelingMessage.textContent = error.message;
  } finally {
    labelRequestInProgress = false;
    allLabelButtons.forEach((button) => { button.disabled = false; });
    skipCropButton.disabled = false;
    undoCropLabelButton.disabled = labelHistory.length === 0;
    renderPreliminarySuggestion(selectedCrop());
  }
}

function confirmPreliminaryLabel() {
  const label = confirmablePreliminaryLabel(selectedCrop());
  if (!label) {
    labelingMessage.textContent = "The preliminary model has no Open or Closed label to confirm.";
    return;
  }
  labelSelectedCrop(label, "door", true);
}

async function undoLastLabel() {
  const action = labelHistory[labelHistory.length - 1];
  if (!action || labelRequestInProgress) return;
  labelRequestInProgress = true;
  allLabelButtons.forEach((button) => { button.disabled = true; });
  skipCropButton.disabled = true;
  confirmPreliminaryButton.disabled = true;
  undoCropLabelButton.disabled = true;
  labelingMessage.textContent = "Undoing the last label...";

  try {
    const response = await fetch("/api/training/crops/labels/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ crop_ids: action.cropIds, dimension: action.dimension }),
    });
    if (!response.ok) throw new Error("Could not undo the last label.");
    labelHistory.pop();
    labelingMessage.textContent = `${action.cropIds.length} label${action.cropIds.length === 1 ? "" : "s"} undone. Classify again.`;
    await loadTrainingQueue();
  } catch (error) {
    labelingMessage.textContent = error.message;
  } finally {
    labelRequestInProgress = false;
    allLabelButtons.forEach((button) => { button.disabled = false; });
    skipCropButton.disabled = false;
    undoCropLabelButton.disabled = labelHistory.length === 0;
    renderPreliminarySuggestion(selectedCrop());
  }
}

labelButtons.forEach((button) => {
  button.addEventListener("click", () => labelSelectedCrop(button.dataset.cropLabel, "door"));
});
runLabelButtons.forEach((button) => {
  button.addEventListener("click", () => labelSelectedCropRun(button.dataset.cropRunLabel, "door"));
});
vehicleLabelButtons.forEach((button) => {
  button.addEventListener("click", () => labelSelectedCrop(button.dataset.vehicleLabel, "vehicle"));
});
vehicleRunLabelButtons.forEach((button) => {
  button.addEventListener("click", () => labelSelectedCropRun(button.dataset.vehicleRunLabel, "vehicle"));
});
skipCropButton.addEventListener("click", skipSelectedCrop);
confirmPreliminaryButton.addEventListener("click", confirmPreliminaryLabel);
undoCropLabelButton.addEventListener("click", undoLastLabel);
refreshUnlabeledCropsButton.addEventListener("click", loadTrainingQueue);
loadMoreCropsButton.addEventListener("click", () => loadUnlabeledCrops({ append: true }));
unlabeledRoomFilter.addEventListener("change", () => {
  labelingMessage.textContent = "";
  loadUnlabeledCrops();
});
unlabeledStatusFilter.addEventListener("change", () => {
  labelingMessage.textContent = "";
  loadUnlabeledCrops();
});
[doorLabelFilter, vehicleLabelFilter].forEach((filter) => {
  filter.addEventListener("change", () => {
    labelingMessage.textContent = "";
    loadUnlabeledCrops();
  });
});
unlabeledCropList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-select-crop]");
  if (!button) return;
  const index = unlabeledCrops.findIndex((crop) => crop.id === Number(button.dataset.selectCrop));
  if (index === -1) return;
  selectedCropIndex = index;
  labelingMessage.textContent = "";
  renderUnlabeledCrops();
});

document.addEventListener("keydown", (event) => {
  if (batchApprovalDialog.open) return;
  if (event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
  const labelByKey = {
    o: "open",
    c: "closed",
    p: "partial",
    u: "unsure",
    b: "bad",
  };
  const vehicleLabelByKey = {
    v: "present",
    n: "absent",
    x: "not_observable",
    "?": "unsure",
  };
  const key = event.key.toLowerCase();
  if (event.shiftKey && ["o", "c", "p"].includes(key)) {
    event.preventDefault();
    labelSelectedCropRun(labelByKey[key], "door");
  } else if (event.shiftKey && ["v", "n", "x"].includes(key)) {
    event.preventDefault();
    labelSelectedCropRun(vehicleLabelByKey[key], "vehicle");
  } else if (event.code === "Space") {
    event.preventDefault();
    confirmPreliminaryLabel();
  } else if (labelByKey[key]) {
    event.preventDefault();
    labelSelectedCrop(labelByKey[key], "door");
  } else if (vehicleLabelByKey[event.key]) {
    event.preventDefault();
    labelSelectedCrop(vehicleLabelByKey[event.key], "vehicle");
  } else if (key === "s" || event.key === "ArrowRight") {
    event.preventDefault();
    skipSelectedCrop();
  }
});

loadTrainingQueue();
window.setInterval(() => {
  if (!labelRequestInProgress && selectedCrop() && !selectedCrop().preliminary_label) {
    loadUnlabeledCrops();
  }
}, 10_000);

function datasetExportPayload() {
  return {
    export_mode: exportMode.value,
    captured_from: exportCapturedFrom.value || null,
    captured_through: exportCapturedThrough.value || null,
    low_confidence_threshold: Number(exportLowConfidence.value) / 100,
    probability_margin_threshold: Number(exportProbabilityMargin.value) / 100,
    random_sample_percent: Number(exportRandomPercent.value),
    duplicate_window_minutes: Number(exportDuplicateWindow.value),
    perceptual_distance: Number(exportPerceptualDistance.value),
    validation_percent: Number(exportValidationPercent.value),
    initial_test_percent: Number(exportTestPercent.value),
    minimum_class_percent: Number(exportMinimumClassPercent.value),
    vehicle_minimum_class_percent: Number(exportVehicleMinimumClassPercent.value),
    include_low_confidence: exportIncludeLowConfidence.checked,
    include_misclassified: exportIncludeMisclassified.checked,
    include_edge_cases: exportIncludeEdgeCases.checked,
  };
}

function classCountTotal(counts) {
  return Object.values(counts).reduce((sum, value) => sum + value, 0);
}

function classCountSummary(counts) {
  return Object.entries(counts)
    .map(([label, count]) => `<b>${count.toLocaleString()}</b> ${escapeHtml(displayLabel(label))}`)
    .join(" · ");
}

function previewCountCard(title, counts) {
  return `<div><strong>${classCountTotal(counts).toLocaleString()}</strong><span>${escapeHtml(title)}</span><small>${classCountSummary(counts)}</small></div>`;
}

function renderDatasetPreview(preview) {
  datasetPreviewTaskCounts.innerHTML = Object.entries(preview.task_counts)
    .map(([task, splits]) => {
      const queried = preview.queried_task_counts[task];
      const exported = Object.fromEntries(
        Object.keys(queried).map((label) => [
          label,
          Object.values(splits).reduce((sum, counts) => sum + counts[label], 0),
        ]),
      );
      return `
        <section class="dataset-task-count-group">
          <h4>${escapeHtml(displayLabel(task))} targets</h4>
          <div class="dataset-preview-stats">
            ${previewCountCard("Queried", queried)}
            ${previewCountCard("Export Total", exported)}
            ${previewCountCard("Train", splits.train)}
            ${previewCountCard("Validation", splits.val)}
            ${previewCountCard("Test", splits.test)}
          </div>
        </section>
      `;
    })
    .join("");
  datasetPreviewMessage.textContent = `Removed ${preview.duplicates_removed.toLocaleString()} duplicates, skipped ${preview.routine_images_skipped.toLocaleString()} routine images, and removed ${preview.class_balance_removed.toLocaleString()} majority-class images for balance.`;
}

async function refreshDatasetPreview() {
  refreshDatasetPreviewButton.disabled = true;
  datasetPreviewMessage.textContent = "Calculating image counts...";
  try {
    const response = await fetch("/api/training/dataset/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datasetExportPayload()),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Could not calculate export counts.");
    renderDatasetPreview(result);
  } catch (error) {
    datasetPreviewMessage.textContent = error.message;
  } finally {
    refreshDatasetPreviewButton.disabled = false;
  }
}

const datasetExportInputs = [
  exportMode,
  exportCapturedFrom,
  exportCapturedThrough,
  exportLowConfidence,
  exportProbabilityMargin,
  exportRandomPercent,
  exportDuplicateWindow,
  exportPerceptualDistance,
  exportValidationPercent,
  exportTestPercent,
  exportMinimumClassPercent,
  exportVehicleMinimumClassPercent,
  exportIncludeLowConfidence,
  exportIncludeMisclassified,
  exportIncludeEdgeCases,
];
datasetExportInputs.forEach((input) => {
  input.addEventListener("change", () => {
    datasetPreviewMessage.textContent = "Settings changed — refresh counts to update the preview.";
  });
});
refreshDatasetPreviewButton.addEventListener("click", refreshDatasetPreview);
exportMinimumClassPercent.addEventListener("input", () => {
  exportMinimumClassValue.textContent = `${Number(exportMinimumClassPercent.value).toFixed(0)}%`;
  datasetPreviewMessage.textContent = "Settings changed — refresh counts to update the preview.";
});
exportVehicleMinimumClassPercent.addEventListener("input", () => {
  exportVehicleMinimumClassValue.textContent = `${Number(exportVehicleMinimumClassPercent.value).toFixed(0)}%`;
  datasetPreviewMessage.textContent = "Settings changed — refresh counts to update the preview.";
});
refreshDatasetPreview();

exportDatasetButton.addEventListener("click", async () => {
  exportDatasetButton.disabled = true;
  downloadDatasetLink.hidden = true;
  datasetExportMessage.textContent = "Building the dataset and ZIP archive...";

  try {
    const response = await fetch("/api/training/dataset/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datasetExportPayload()),
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.detail || "Dataset export failed.");
    const splitCounts = Object.entries(result.task_counts)
      .map(([task, splits]) => {
        const total = Object.values(splits).reduce(
          (splitSum, counts) => splitSum + classCountTotal(counts),
          0,
        );
        return `${displayLabel(task)}: ${total}`;
      })
      .join(", ");
    const benchmarkText = result.benchmark_created
      ? " Created the fixed benchmark test set."
      : " Reused the fixed benchmark test set.";
    datasetExportMessage.textContent = `${result.dataset_version}: exported ${result.images_exported} file${result.images_exported === 1 ? "" : "s"} (${splitCounts}). Removed ${result.duplicates_removed} duplicates, skipped ${result.routine_images_skipped} routine images, removed ${result.class_balance_removed} class targets for balance, and found ${result.conflicting_duplicates} conflicting duplicates.${benchmarkText}`;
    downloadDatasetLink.href = result.archive_url;
    downloadDatasetLink.hidden = false;
    await refreshDatasetPreview();
  } catch (error) {
    datasetExportMessage.textContent = error.message;
  } finally {
    exportDatasetButton.disabled = false;
  }
});
