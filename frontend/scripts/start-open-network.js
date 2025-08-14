/*
  Starts the CRA/CRACO dev server without auto-opening localhost and
  automatically opens the "On Your Network" URL instead when it's ready.
  - Cross-platform browser open (Windows/macOS/Linux)
  - No extra dependencies
*/

const { spawn } = require('child_process');
const path = require('path');

// We'll invoke the dev server through Yarn to avoid direct module path resolution issues.
// Using Yarn ensures @craco/craco is executed from node_modules/.bin regardless of dev/prod env.
const YARN_CMD = process.platform === 'win32' ? 'yarn.cmd' : 'yarn';

function openUrl(url) {
  const platform = process.platform;
  try {
    if (platform === 'win32') {
      // Use Windows shell to open default browser (shell needed for Windows)
      spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore', shell: true });
    } else if (platform === 'darwin') {
      // macOS
      spawn('open', [url], { detached: true, stdio: 'ignore' });
    } else {
      // Linux and others
      const opener = process.env.BROWSER || 'xdg-open';
      const child = spawn(opener, [url], { detached: true, stdio: 'ignore' });
      child.on('error', () => {
        console.log(`\n[dev] Could not auto-open browser. Please open: ${url}`);
      });
    }
  } catch (e) {
    console.log(`\n[dev] Could not auto-open browser. Please open: ${url}`);
  }
}

let opened = false;
let stdoutBuffer = '';
let stderrBuffer = '';

const env = { ...process.env, BROWSER: 'none' };

// Optional: bind to all interfaces if HOST not set to ensure network URL is available
if (!env.HOST) env.HOST = '0.0.0.0';

// Robust cross-platform spawn for dev server using shell to avoid Windows spawn EINVAL issues
const cwd = path.resolve(__dirname, '..');
const binDir = path.resolve(cwd, 'node_modules', '.bin');
const cracoBinWin = path.join(binDir, 'craco.cmd');
const cracoBinNix = path.join(binDir, 'craco');

let child;
if (process.platform === 'win32') {
  // Use cmd to run the .cmd shim on Windows to avoid spawn EINVAL
  child = spawn('cmd', ['/c', cracoBinWin, 'start'], {
    cwd,
    env,
    stdio: ['inherit', 'pipe', 'pipe'],
    shell: false,
  });
} else {
  child = spawn(cracoBinNix, ['start'], {
    cwd,
    env,
    stdio: ['inherit', 'pipe', 'pipe'],
    shell: false,
  });
}

const networkUrlRegex = /On Your Network:\s*(https?:\/\/[^\s]+)/i;

function handleChunk(chunk, streamName) {
  const text = chunk.toString();
  if (streamName === 'stdout') stdoutBuffer += text; else stderrBuffer += text;
  process[streamName].write(text);

  const lines = (streamName === 'stdout' ? stdoutBuffer : stderrBuffer).split(/\r?\n/);
  // Keep the last partial line in buffer
  if (streamName === 'stdout') stdoutBuffer = lines.pop() || ''; else stderrBuffer = lines.pop() || '';

  for (const line of lines) {
    if (!opened) {
      const m = line.match(networkUrlRegex);
      if (m && m[1]) {
        const url = m[1].trim();
        opened = true;
        console.log(`\n[dev] Opening network URL: ${url}\n`);
        openUrl(url);
      }
    }
  }
}

child.stdout.on('data', (d) => handleChunk(d, 'stdout'));
child.stderr.on('data', (d) => handleChunk(d, 'stderr'));

child.on('close', (code) => {
  if (!opened) {
    // Fallback: try to compute a likely network URL if parsing failed
    const port = process.env.PORT || '3000';
    try {
      const os = require('os');
      const ifaces = os.networkInterfaces();
      for (const name of Object.keys(ifaces)) {
        for (const iface of ifaces[name] || []) {
          if (iface && iface.family === 'IPv4' && !iface.internal) {
            const url = `http://${iface.address}:${port}`;
            console.log(`\n[dev] Dev server closed (code ${code}). You can try opening: ${url}`);
            return;
          }
        }
      }
    } catch (_) {}
  }
  process.exit(code ?? 0);
});