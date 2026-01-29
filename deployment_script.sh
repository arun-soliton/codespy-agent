# Step 1: Install Docker
echo "Updating APT..."
sudo apt-get update

echo "Installing required packages..."
sudo apt-get install -y ca-certificates curl gnupg lsb-release

echo "Adding Docker's official GPG key..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "Setting up the stable Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "Updating APT with the new Docker repository..."
sudo apt-get update

echo "Installing Docker CE, CLI, and containerd.io..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Step 2: Auto start Docker
echo "Enabling Docker to start on boot..."
sudo systemctl enable docker

# Step 3: Setup Qdrant using Docker Compose
echo "Creating a directory for Qdrant and Neo4j and navigating into it..."
sudo mkdir -p ~/db_setup && cd ~/db_setup

echo "Creating docker-compose.yaml..."
sudo tee docker-compose.yaml > /dev/null <<EOF
services:
  neo4j:
    image: neo4j:latest
    container_name: neo4j-graph-db
    restart: always
    volumes:
      - neo4j_logs:/logs
      - neo4j_data:/data
      - neo4j_plugins:/plugins
    environment:
      - NEO4J_AUTH=neo4j/secret_code
      - NEO4J_PLUGINS='["apoc"]'
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
      - NEO4J_apoc_import_file_use__neo4j__config=true
    ports:
      - "7474:7474"
      - "7687:7687"

  qdrant:
    image: qdrant/qdrant:latest
    restart: always
    container_name: qdrant-vector-db
    ports:
      - "6333:6333"
      - "6334:6334"
    environment:
      - QDRANT__SERVICE__API_KEY=secret_code
    configs:
      - source: qdrant_config
        target: /qdrant/config/production.yaml
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_plugins:
  qdrant_data:

configs:
  qdrant_config:
    content: |
      log_level: INFO
EOF

echo "Creating the 'db' directory..."
sudo mkdir -p db

# Note: Configure Azure NSG to allow inbound traffic on ports:
# ufw is not needed here - update if needed to configure firewall rules
# - 6333, 6334 (Qdrant)
# - 7474, 7687 (Neo4j)

# Step 4: Run the container
echo "Run the container"
sudo docker compose up -d

echo "Setup completed successfully!"