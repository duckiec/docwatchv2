import docker
import time
import sys

def cleanup(client, name):
    try:
        container = client.containers.get(name)
        print(f"Cleaning up {name}...")
        container.remove(force=True)
    except docker.errors.NotFound:
        pass

def run_scenario(client, name, image, command, env, expected_fail=True):
    print(f"\n--- Running Scenario: {name} ---")
    cleanup(client, name)

    try:
        container = client.containers.run(
            image,
            command,
            name=name,
            environment=env,
            detach=True
        )
        print(f"Container {name} started. Waiting for exit...")
        result = container.wait()

        exit_code = result.get("StatusCode", -1)
        print(f"Container exited with code: {exit_code}")

        if expected_fail and exit_code == 0:
            print("❌ WARNING: Expected failure, but exited cleanly.")
        elif not expected_fail and exit_code != 0:
            print("❌ WARNING: Expected success, but failed.")
        else:
            print("✅ Scenario executed as expected.")

    except Exception as e:
        print(f"Error running scenario: {e}")
    finally:
        # Give DocWatch a moment to process before cleaning up the docker engine reference
        time.sleep(2)

def main():
    client = docker.from_env()
    print("Starting Comprehensive Test Scenarios for DocWatch V2")

    # Scenario 1: Immediate failure due to missing config (Simulating App crash)
    run_scenario(
        client,
        name="test-crash-missing-env",
        image="alpine:latest",
        command="sh -c 'if [ -z \"$REQUIRED_VAR\" ]; then echo \"FATAL: REQUIRED_VAR missing\"; exit 1; fi'",
        env={"SENSITIVE_TOKEN": "my-super-secret-password-123"}, # Should be masked by new security feature
        expected_fail=True
    )

    # Scenario 2: OOM Kill Simulation
    # Note: actually triggering OOM on host can be tricky in simple tests without stressing the daemon.
    # We will simulate an out of memory script failure instead.
    run_scenario(
        client,
        name="test-crash-memory-exhaustion",
        image="python:3.11-slim",
        command="python -c \"print('Starting memory intensive task...'); a = []; [a.append(' ' * 10**6) for i in range(1000)]; print('Done')\"",
        env={"DB_PASSWORD": "db-secret-password"},
        expected_fail=True
    )

    # Scenario 3: Syntax error in command
    run_scenario(
        client,
        name="test-crash-syntax-error",
        image="alpine:latest",
        command="sh -c '/bin/bash -c \"echo Hello\"'", # Alpine doesn't have bash by default
        env={"API_KEY": "sk-1234567890abcdef"},
        expected_fail=True
    )

    print("\nAll scenarios dispatched. Check DocWatch UI to verify incidents and masked env vars.")

if __name__ == '__main__':
    main()
