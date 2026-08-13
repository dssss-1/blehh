import threading

counter = 0

def increment():
    global counter
    for _ in range(100000):
        counter += 1

threads = []

for _ in range(10):
    t = threading.Thread(target=increment)
    threads.append(t)

# Synchronize access to the shared variable using a lock
lock = threading.Lock()

with lock:
    for t in threads:
        t.start()
    for t in threads:
        t.join()

print(counter)