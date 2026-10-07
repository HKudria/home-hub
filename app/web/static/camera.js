/* Camera capture for the add-medicine flow.
 *
 * Two photo slots. Tapping a camera button opens the device camera
 * (environment-facing); the frame is drawn to a canvas and captured as
 * JPEG (quality 0.8). If the camera is unavailable or permission is
 * denied, a plain file input appears as fallback. Shots are POSTed to
 * /extract; the JSON response fills the form fields (or shows a
 * "several packages" / generic error message).
 */
(function () {
  "use strict";

  var MAX_SLOTS = 2;
  var MSGS = window.CAMERA_MSGS || {};
  var shots = [null, null]; // Blob per slot, slot 0 is the primary photo.

  var msgEl = document.getElementById("camera-msg");
  var previewWrap = document.getElementById("camera-preview-wrap");
  var video = document.getElementById("camera-preview");
  var captureBtn = document.getElementById("camera-capture");
  var cancelBtn = document.getElementById("camera-cancel");
  var cameraBtns = Array.prototype.slice.call(document.querySelectorAll(".camera-btn"));
  var fileInputs = Array.prototype.slice.call(document.querySelectorAll(".file-fallback"));

  var stream = null;
  var activeSlot = null;

  function showMsg(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.classList.remove("hidden");
    msgEl.classList.toggle("camera-msg-error", !!isError);
  }

  function hideMsg() {
    if (msgEl) msgEl.classList.add("hidden");
  }

  function stopStream() {
    if (stream) {
      stream.getTracks().forEach(function (t) { t.stop(); });
      stream = null;
    }
    if (previewWrap) previewWrap.classList.add("hidden");
  }

  function startCamera(slot) {
    activeSlot = slot;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      fallback(slot);
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        previewWrap.classList.remove("hidden");
        hideMsg();
      })
      .catch(function () {
        fallback(slot);
      });
  }

  /* Camera denied/unavailable: reveal the file input for this slot. */
  function fallback(slot) {
    stopStream();
    var input = fileInputs[slot];
    if (input) {
      input.classList.remove("hidden");
      input.click();
    } else {
      showMsg(MSGS.aiError || "Camera unavailable.", true);
    }
  }

  captureBtn.addEventListener("click", function () {
    if (!stream || activeSlot === null) return;
    var canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    if (!canvas.width || !canvas.height) return;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(function (blob) {
      if (blob) {
        shots[activeSlot] = blob;
        upload();
      }
      stopStream();
    }, "image/jpeg", 0.8);
  });

  cancelBtn.addEventListener("click", stopStream);

  cameraBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      startCamera(parseInt(btn.dataset.slot, 10) || 0);
    });
  });

  fileInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      var slot = parseInt(input.dataset.slot, 10) || 0;
      var file = input.files && input.files[0];
      if (file) {
        shots[slot] = file;
        upload();
      }
    });
  });

  function setField(name, value) {
    if (value === null || value === undefined) return;
    var el = document.querySelector('[name="' + name + '"]');
    if (el && value !== "") el.value = value;
  }

  function upload() {
    var blobs = shots.filter(Boolean);
    if (!blobs.length) return;
    var fd = new FormData();
    blobs.forEach(function (b, i) {
      fd.append("images", b, "photo" + i + ".jpg");
    });
    fetch("/extract", { method: "POST", body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.multiple) {
          showMsg(MSGS.multiple || "Please photograph one box at a time.", true);
        } else if (data.error) {
          if (data.photo_saved) {
            document.getElementById("photo_saved").value = data.photo_saved;
          }
          document.getElementById("ai_failed").value = "1";
          showMsg(MSGS.aiError || "Could not read the photo.", true);
        } else {
          document.getElementById("photo_saved").value = data.photo_saved || "";
          document.getElementById("ai_extracted").value = "1";
          document.getElementById("ai_failed").value = "";
          setField("name", data.name);
          setField("active_ingredient", data.active_ingredient);
          setField("form", data.form);
          ["pl", "ru", "uk", "en"].forEach(function (code) {
            setField("dosage_" + code, data["dosage_" + code]);
            setField("description_" + code, data["description_" + code]);
          });
          if (data.expiry_date) setField("expiry_date", data.expiry_date);
          showMsg(MSGS.aiOk || "Photo read.", false);
        }
      })
      .catch(function () {
        document.getElementById("ai_failed").value = "1";
        showMsg(MSGS.aiError || "Could not read the photo.", true);
      });
  }
})();
