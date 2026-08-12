const PREFERRED_VIDEO_CONSTRAINTS = {
  video: {
    facingMode: { ideal: 'environment' },
    width: { ideal: 1920 },
    height: { ideal: 1080 },
  },
  audio: false,
}

/**
 * Start the rear camera on phones when available, while always falling back
 * to the laptop/webcam camera. A facingMode "ideal" constraint is compatible
 * with browsers that do not expose a rear camera.
 */
function cameraErrorMessage(error) {
  switch (error?.name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return 'Camera permission was blocked. In Chrome, tap the lock icon beside the address, allow Camera, then reload this page.'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'No camera was found. Connect or enable a camera, then try again.'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'The camera is being used by another app. Close other camera apps, then try again.'
    case 'OverconstrainedError':
      return 'This camera does not support the requested settings. Please try again.'
    case 'SecurityError':
      return 'Camera access requires a secure HTTPS connection.'
    default:
      return 'Camera access failed. Please allow camera permission and try again.'
  }
}

export async function openCaptureCamera() {
  if (!window.isSecureContext) {
    throw new Error('Camera access requires a secure HTTPS connection.')
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser does not support live camera capture. Use “Use phone camera” instead.')
  }

  const attempts = [
    PREFERRED_VIDEO_CONSTRAINTS,
    { video: { facingMode: { ideal: 'environment' } }, audio: false },
    { video: true, audio: false },
  ]
  let lastError
  for (const constraints of attempts) {
    try {
      return await navigator.mediaDevices.getUserMedia(constraints)
    } catch (error) {
      lastError = error
      // A permission/security error cannot be resolved by trying a different
      // constraint. Stop immediately and show the actionable browser guidance.
      if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError' || error?.name === 'SecurityError') break
    }
  }
  throw new Error(cameraErrorMessage(lastError))
}

export async function attachCameraStream(video, stream) {
  if (!video) {
    stream?.getTracks().forEach((track) => track.stop())
    throw new Error('Camera preview is not ready.')
  }

  try {
    // Register listeners before assigning srcObject. Some Android devices can
    // emit loadedmetadata immediately, before a listener added afterwards.
    const metadataReady = video.readyState >= HTMLMediaElement.HAVE_METADATA
      ? Promise.resolve()
      : new Promise((resolve, reject) => {
          const timeoutId = window.setTimeout(() => {
            cleanup()
            reject(new Error('Camera did not provide a video frame.'))
          }, 8000)
          const cleanup = () => {
            window.clearTimeout(timeoutId)
            video.removeEventListener('loadedmetadata', onLoaded)
            video.removeEventListener('error', onError)
          }
          const onLoaded = () => {
            cleanup()
            resolve()
          }
          const onError = () => {
            cleanup()
            reject(new Error('Camera preview could not be started.'))
          }
          video.addEventListener('loadedmetadata', onLoaded, { once: true })
          video.addEventListener('error', onError, { once: true })
        })

    video.srcObject = stream
    await metadataReady
    await video.play()
  } catch (error) {
    stream?.getTracks().forEach((track) => track.stop())
    video.srcObject = null
    throw error
  }
}

/** Capture a high-quality JPEG only after the video has real dimensions. */
export async function captureCameraPhoto(video, filename = 'capture.jpg') {
  const sourceWidth = video?.videoWidth || 0
  const sourceHeight = video?.videoHeight || 0
  if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !sourceWidth || !sourceHeight) {
    throw new Error('Camera is still starting. Wait for the preview, then capture again.')
  }

  const longestSide = Math.max(sourceWidth, sourceHeight)
  const scale = longestSide > 1920 ? 1920 / longestSide : 1
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(sourceWidth * scale))
  canvas.height = Math.max(1, Math.round(sourceHeight * scale))
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Unable to create a camera image.')
  context.drawImage(video, 0, 0, canvas.width, canvas.height)

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.95))
  if (!blob) throw new Error('Unable to capture the camera image.')
  return new File([blob], filename, { type: 'image/jpeg' })
}
