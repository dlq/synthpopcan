let nextJobId = 1;

export function runBrowserJob(job) {
  return new Promise((resolve, reject) => {
    const id = nextJobId;
    nextJobId += 1;
    const worker = new Worker(new URL("./worker.mjs", import.meta.url), {
      type: "module",
    });
    worker.addEventListener("message", (event) => {
      if (event.data.id !== id) {
        return;
      }
      worker.terminate();
      if (event.data.ok) {
        resolve(event.data.result);
      } else {
        reject(new Error(event.data.error));
      }
    });
    worker.addEventListener("error", (error) => {
      worker.terminate();
      reject(error);
    });
    worker.postMessage({ id, job });
  });
}
