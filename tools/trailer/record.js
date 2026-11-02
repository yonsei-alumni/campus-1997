// 신촌 캠퍼스 1997 trailer: paste into the browser console on the running game (npm run dev), with
// `python3 tools/trailer/frame_server.py <frames dir>` running.  Renders 46 s at 30 fps, 1920x1080, frame by frame
// (window.__y97.record steps the game loop at a fixed time, so a slow or background tab still gives smooth video):
// a bird's-eye flight over the campus, down onto 백양로 as in the 1997 aerial photo, then a swoop down behind the walker
// who walks up 백양로 toward 중앙도서관.  Then: python3 tools/trailer/make_video.py <dir with frames/> out.mp4
(async () => {
  const y = window.__y97, B = y.bird, FPS = 30, T = 46;
  // bird's-eye keyframes: t, x, y, dist, pitch, yaw (campus frame)
  const K = [[0, -30, -60, 640, 0.62, -0.45], [7, -20, -50, 600, 0.66, 0.12], [13, -85, -310, 230, 0.42, 0.24],
    [19, -60, -205, 110, 0.26, 0.24], [23, -48, -140, 40, 0.16, 0.24]];
  const ease = (u) => u * u * (3 - 2 * u);
  const at = (t) => {
    let i = 0;
    while (i < K.length - 2 && t > K[i + 1][0]) i++;
    const a = K[i], b = K[i + 1];
    const u = ease(Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))));
    const v = a.map((x, k) => x + (b[k] - x) * u);
    return { x: v[1], y: v[2], dist: v[3], pitch: v[4], yaw: v[5] };
  };
  y.setSeason('summer');
  await new Promise((r) => setTimeout(r, 2500));
  y.startWalk();
  y.player.keys.clear();
  y.player.teleport(-47, -128, -0.24);          // west sidewalk below the library, facing up 백양로
  y.enterBird();
  B.auto = false;
  y.record.start(1920, 1080);
  let walked = false, left = false;
  for (let i = 0; i < T * FPS; i++) {
    const t = i / FPS;
    if (t < 23) { const k = at(t); Object.assign(B.goal, k); Object.assign(B.cur, k); }
    else if (!left) { y.leaveBird(); left = true; }
    if (t >= 24.2 && !walked) { y.player.keys.add('KeyW'); walked = true; }
    y.record.step(1 / FPS);
    const blob = await new Promise((res) => y.renderer.domElement.toBlob(res, 'image/jpeg', 0.92));
    await fetch('http://127.0.0.1:8765/f/' + String(i).padStart(5, '0'), { method: 'POST', body: blob });
  }
  y.player.keys.clear();
  y.record.stop();
  console.log('trailer frames done');
})();
