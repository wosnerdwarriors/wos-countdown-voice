export function navigateToRoom(id) {
  const url = new URL(window.location.href);
  url.searchParams.set("instance_id", id);
  window.location.href = url.toString();
}

export function createRandomRoomId() {
  return Math.random().toString(36).slice(2, 8).toUpperCase();
}

export function leaveRoom() {
  const url = new URL(window.location.href);
  url.searchParams.delete("instance_id");
  window.location.href = url.toString();
}
