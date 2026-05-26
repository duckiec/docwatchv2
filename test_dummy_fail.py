import docker

def main():
    client = docker.from_env()
    print("Starting failing dummy container...")
    try:
        # First, remove it if it exists from previous run
        try:
            old_container = client.containers.get("dummy-failing-container")
            old_container.remove(force=True)
        except docker.errors.NotFound:
            pass

        container = client.containers.run(
            "alpine:latest",
            "sh -c \"echo 'failing now' && sleep 1 && /bin/false\"",
            name="dummy-failing-container",
            detach=True
        )
        container.wait()
        print("Container finished (failed as expected).")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
