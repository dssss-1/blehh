import threading

counter = 0

def increment(lock):
    global counter
    for _ in range(100000):
        with lock:
            counter += 1

lock = threading.Lock()

threads = []

for _ in range(10):
    t = threading.Thread(target=increment, args=(lock,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(counter)