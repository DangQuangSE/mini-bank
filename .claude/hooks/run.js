const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Helper to find python executable on Windows
function findPythonWindows() {
  // If PYTHON env var is set, use it
  if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
    return process.env.PYTHON;
  }
  
  // Try using `py` launcher first
  try {
    const { execSync } = require('child_process');
    execSync('py --version', { stdio: 'ignore' });
    return 'py';
  } catch (e) {}

  // Try parsing PATH to find a real python.exe (excluding WindowsApps)
  const pathEnv = process.env.PATH || '';
  const pathDirs = pathEnv.split(path.delimiter);
  for (const dir of pathDirs) {
    if (dir.toLowerCase().includes('windowsapps')) {
      continue;
    }
    const pyPath = path.join(dir, 'python.exe');
    if (fs.existsSync(pyPath)) {
      return pyPath;
    }
  }

  // Fallback to python
  return 'python';
}

function getPythonCmd() {
  if (os.platform() === 'win32') {
    const py = findPythonWindows();
    return py === 'py' ? ['py', '-3'] : [py];
  } else {
    // On Unix, try python3 first
    return ['python3'];
  }
}

const args = process.argv.slice(2);
if (args.length === 0) {
  process.exit(0);
}

const scriptPath = args[0];
const scriptArgs = args.slice(1);

const pyCmdInfo = getPythonCmd();
const pyExecutable = pyCmdInfo[0];
const spawnArgs = [...pyCmdInfo.slice(1), scriptPath, ...scriptArgs];

const child = spawn(pyExecutable, spawnArgs, {
  stdio: ['pipe', 'pipe', 'pipe']
});

// Pipe stdin to the python child process
process.stdin.pipe(child.stdin);

// Pipe stdout from python child process
child.stdout.on('data', (data) => {
  process.stdout.write(data);
});

// Pipe stderr from python child process
child.stderr.on('data', (data) => {
  process.stderr.write(data);
});

child.on('close', (code) => {
  process.exit(code === null ? 1 : code);
});

child.on('error', (err) => {
  // If python3 failed on Unix/macOS, retry with python
  if (os.platform() !== 'win32' && pyExecutable === 'python3' && err.code === 'ENOENT') {
    const fallbackChild = spawn('python', [scriptPath, ...scriptArgs], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    process.stdin.pipe(fallbackChild.stdin);
    fallbackChild.stdout.on('data', (data) => process.stdout.write(data));
    fallbackChild.stderr.on('data', (data) => process.stderr.write(data));
    fallbackChild.on('close', (code) => process.exit(code === null ? 1 : code));
    fallbackChild.on('error', (fallbackErr) => {
      console.error('Failed to start python:', fallbackErr.message);
      process.exit(127);
    });
    return;
  }
  console.error('Failed to start python process:', err.message);
  process.exit(127);
});
