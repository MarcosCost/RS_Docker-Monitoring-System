import sys
import os

"""
RS Agent Injector (Zero-Dependency & Interactive)
Automatically adds monitoring sidecars and injects UDP ports.
Robust block-based parsing to prevent data loss.
"""

AGENT_TEMPLATE = """
  agent-{name}:
    build: ../agent
    container_name: agent-{name}
    network_mode: "service:{name}"
    depends_on:
      - {name}
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - MY_CONTAINER_NAME=agent-{name}
      - PYTHONUNBUFFERED=1

      
"""

UDP_RELAY_TEMPLATE = """
  udp-relay:
    image: alpine/socat
    container_name: udp-relay
    ports:
      - \"9999:9999/udp\" 
    command: udp-listen:9999,fork,reuseaddr udp-datagram:172.25.255.255:9999,broadcast

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
"""

def inject_agents(input_file, output_file):
    with open(input_file, 'r') as f:
        lines = f.readlines()

    new_lines = []
    services_found = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 1. Look for 'services:' header
        if stripped == "services:":
            services_found = True
            new_lines.append(line)
            i += 1
            continue

        # 2. If we are in services, look for service definitions (2 spaces indent)
        if services_found and line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            service_name = stripped[:-1].strip()
            
            # Capture the entire service block
            block = [line]
            j = i + 1
            while j < len(lines) and (lines[j].startswith("    ") or lines[j].strip() == "" or lines[j].startswith("  #")):
                block.append(lines[j])
                j += 1
            
            # Update main loop index to where the block ends
            i = j
            
            # Skip if it's already an agent or infra
            is_infra = any(x in service_name.lower() for x in ['agent-', 'broker', 'monitor', 'dashboard'])
            if is_infra:
                new_lines.extend(block)
                continue

            # --- Process Target Service ---
            print(f"  > Processing service: {service_name}")
            
            has_container_name = any("container_name:" in l.strip() for l in block)
            
            if not has_container_name:
                print(f"WARNING: Service '{service_name}' does not have a 'container_name' defined!")

            # Add the block
            new_lines.extend(block)
            
            # Append the Agent template
            new_lines.append(AGENT_TEMPLATE.format(name=service_name))
            continue

        # 3. Default: just copy the line
        new_lines.append(line)
        i += 1

    # Add UDP Relay and Networks at the end
    new_lines.append(UDP_RELAY_TEMPLATE)

    with open(output_file, 'w') as f:
        f.writelines(new_lines)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("\n--- RS Agent Injector (v2.0) ---")
    print(f"Context directory: {script_dir}")
    
    try:
        rel_path = input("\nEnter the path to the Docker Compose file (relative to this script): ").strip()
    except EOFError:
        return

    if not rel_path:
        print("No path provided. Exiting.")
        return

    input_path = os.path.abspath(os.path.join(script_dir, rel_path))

    if not os.path.exists(input_path):
        print(f"Error: File not found at '{input_path}'")
        return

    input_filename = os.path.basename(input_path)
    output_filename = input_filename.replace('.yaml', '.monitored.yaml').replace('.yml', '.monitored.yml')
    
    if output_filename == input_filename:
        output_filename = "docker-compose.monitored.yml"

    output_path = os.path.join(script_dir, output_filename)

    print(f"\nProcessing '{input_filename}'...")
    try:
        inject_agents(input_path, output_path)
        print(f"\nSUCCESS! Monitored file created: {output_filename}")
        print(f"Full output path: {output_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
