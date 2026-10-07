/* Camera capture for the add-medicine flow.
 *
 * A single photo slot. Tapping the camera button opens the device camera
 * (environment-facing); the frame is drawn to a canvas and captured as
 * JPEG (quality 0.8). If the camera is unavailable or permission is
 * denied, a plain file input appears as fallback. The shot is POSTed to
 * /extract; the JSON response fills the form fields (or shows a
 * "several packages" / generic error message).
 */
(function () {
  "use strict";

  var MSGS = window.CAMERA_MSGS || {};
  var shot = null; // The captured Blob (or chosen File).

  var msgEl = document.getElementById("camera-msg");
  var loadingEl = document.getElementById("camera-loading");
  var previewWrap = document.getElementById("camera-preview-wrap");
  var video = document.getElementById("camera-preview");
  var captureBtn = document.getElementById("camera-capture");
  var cancelBtn = document.getElementById("camera-cancel");
  var cameraBtns = Array.prototype.slice.call(document.querySelectorAll(".camera-btn"));
  var fileInputs = Array.prototype.slice.call(document.querySelectorAll(".file-fallback"));

  var stream = null;

  function showMsg(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.classList.remove("hidden");
    msgEl.classList.toggle("camera-msg-error", !!isError);
  }

  function hideMsg() {
    if (msgEl) msgEl.classList.add("hidden");
  }

  /* Busy state while /extract is in flight: show the spinner + text and
   * lock the capture/extract controls so no second upload can start. */
  function setBusy(busy) {
    [captureBtn].concat(cameraBtns, fileInputs).forEach(function (el) {
      if (el) el.disabled = busy;
    });
    if (loadingEl) loadingEl.classList.toggle("hidden", !busy);
  }

  function stopStream() {
    if (stream) {
      stream.getTracks().forEach(function (t) { t.stop(); });
      stream = null;
    }
    if (previewWrap) previewWrap.classList.add("hidden");
  }

  function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      fallback();
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
        fallback();
      });
  }

  /* Camera denied/unavailable: reveal the file input. */
  function fallback() {
    stopStream();
    var input = fileInputs[0];
    if (input) {
      input.classList.remove("hidden");
      input.click();
    } else {
      showMsg(MSGS.aiError || "Camera unavailable.", true);
    }
  }

  captureBtn.addEventListener("click", function () {
    if (!stream) return;
    var canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    if (!canvas.width || !canvas.height) return;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(function (blob) {
      if (blob) {
        shot = blob;
        upload();
      }
      stopStream();
    }, "image/jpeg", 0.8);
  });

  cancelBtn.addEventListener("click", stopStream);

  cameraBtns.forEach(function (btn) {
    btn.addEventListener("click", startCamera);
  });

  fileInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (file) {
        shot = file;
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
    if (!shot) return;
    var fd = new FormData();
    fd.append("images", shot, "photo0.jpg");
    setBusy(true);
    (async function () {
      try {
        var r = await fetch("/extract", { method: "POST", body: fd });
        var data = await r.json();
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
      } catch (e) {
        document.getElementById("ai_failed").value = "1";
        showMsg(MSGS.aiError || "Could not read the photo.", true);
      } finally {
        setBusy(false);
      }
    })();
  }
})();
