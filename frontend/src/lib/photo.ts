/** Shrink a photo on the phone before it is sent.
 *
 *  Drawing it onto a canvas and re-encoding it as JPEG makes it small enough
 *  to send over a weak signal, and drops the camera's metadata, location
 *  included, which the nursery has no need of.
 */

export const MAX_SIDE = 480

export async function shrink(file: File, maxSide = MAX_SIDE): Promise<string> {
  if (!file.type.startsWith('image/')) throw new Error('Choose a photo.')
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(bitmap.width * scale))
  canvas.height = Math.max(1, Math.round(bitmap.height * scale))
  const context = canvas.getContext('2d')
  if (!context) throw new Error('This phone could not prepare the photo.')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', 0.82)
}
