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
export async function openCaptureCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser does not support camera capture.')
  }

  try {
    return await navigator.mediaDevices.getUserMedia(PREFERRED_VIDEO_CONSTRAINTS)
  } catch (preferredError) {
    try {
      return await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    } catch (fallbackError) {
      throw new Error('Camera access failed. Please allow camera permission and try again.')
    }
  }
}

export async function attachCameraStream(video, stream) {
  if (!video) throw new Error('Camera preview is not ready.')

  video.srcObject = stream
  if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
    await new Promise((resolve, reject) => {
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
  }
  await video.play().catch(() => undefined)
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
