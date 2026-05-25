export function getImageUri(imageUris, mode) {
  if (!imageUris) return "";
  return imageUris[mode] || imageUris.normal || imageUris.small || "";
}

export function getExactImageUri(imageUris, mode) {
  if (!imageUris) return "";
  return imageUris[mode] || "";
}
