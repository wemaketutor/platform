import pulumi
import pulumi_docker as docker
from pulumi import Config, export
from pulumi_vault import Provider as VaultProvider, Mount, kv
from pulumi_minio import Provider as MinioProvider, S3Bucket
import os
from dotenv import load_dotenv


load_dotenv("secrets.env")

config = Config()
vault_image = "vault:1.15.0"
vault_port = 8200

vault_provider = VaultProvider(
    "vault-provider",
    address=f"http://localhost:{vault_port}",
    token="root"
)

backend_network = docker.Network("backend-network")
monitoring_network = docker.Network("monitoring-network")

volumes = {
    "db_data": docker.Volume("db-data"),
    "db_data_backups": docker.Volume("db-data-backups"),
    "prometheus_data": docker.Volume("prometheus-data"),
    "grafana_data": docker.Volume("grafana-data"),
    "minio_data": docker.Volume("minio-data")
}

backend_image = docker.Image("")

vault = docker.Container(
    "vault",
    image=vault_image,
    ports=[docker.ContainerPortArgs(
        internal=vault_port,
        external=vault_port,
    )],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=backend_network.name,
        aliases=["vault"],
    )],
    volumes=[docker.ContainerVolumeArgs(
        host_path="/tmp/vault-data",
        container_path="/vault/file",
    )],
    command=["server -dev -dev-root-token-id=root"],
    envs=[
        f"VAULT_ADDR=http://0.0.0.0:{vault_port}",
        f"VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:{vault_port}"
    ],
    restart="unless-stopped",
)

kv_secrets = Mount(
    "kv-secrets",
    path="secret",
    type="kv-v2",
    description="KV Secrets Engine",
    opts=pulumi.ResourceOptions(provider=vault_provider)
)

db_secrets = kv.SecretV2(
    "db-secrets",
    mount=kv_secrets.path,
    data_json=pulumi.Output.json_dumps({
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
    }),
    opts=pulumi.ResourceOptions(provider=vault_provider)
)

grafana_secrets = kv.SecretV2(
    "grafana-secrets",
    mount=kv_secrets.path,
    data_json=pulumi.Output.json_dumps({
        "GF_SECURITY_ADMIN_PASSWORD": os.getenv("GF_SECURITY_ADMIN_PASSWORD"),
    }),
    opts=pulumi.ResourceOptions(provider=vault_provider)
)

backend_secrets = kv.SecretV2(
    "backend-secrets",
    mount=kv_secrets.path,
    data_json=pulumi.Output.json_dumps({
        "SOME_BACKEND_SECRET": os.getenv("BACKEND_SECRET"),
    }),
    opts=pulumi.ResourceOptions(provider=vault_provider)
)

db = docker.Container(
    "db",
    image="postgres:15.2-alpine",
    restart="unless-stopped",
    volumes=[
        docker.ContainerVolumeArgs(
            volume_name=volumes["db_data"].name,
            container_path="/var/lib/postgresql/data",
        ),
        docker.ContainerVolumeArgs(
            volume_name=volumes["db_data_backups"].name,
            container_path="/backups",
        ),
    ],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=backend_network.name,
        aliases=["db"],
    )],
    envs=[
        f"POSTGRES_USER={db_secrets.data.apply(lambda d: d["data"]["POSTGRES_USER"])}",
        f"POSTGRES_PASSWORD={db_secrets.data.apply(lambda d: d["data"]["POSTGRES_PASSWORD"])}",
        f"POSTGRES_DB={db_secrets.data.apply(lambda d: d["data"]["POSTGRES_DB"])}",
    ],
    ports=[docker.ContainerPortArgs(
        internal=5432,
        external=5432,
    )],
)

backend = docker.Container(
    "backend",
    image="backend:dev",
    build=docker.DockerBuildArgs(
        context=".",
        dockerfile="./docker/backend/Dockerfile",
    ),
    depends_on=[db],
    networks_advanced=[
        docker.ContainerNetworksAdvancedArgs(name=backend_network.name),
        docker.ContainerNetworksAdvancedArgs(name=monitoring_network.name),
    ],
    command=["runner"],
    ports=[docker.ContainerPortArgs(
        internal=8081,
        external=8081,
    )],
    envs=[
        "VAULT_ADDR=http://vault:8200",
        "VAULT_TOKEN=root",
        "DB_SECRETS_PATH=secret/data/db",
        f"BACKEND_SECRET={backend_secrets.data.apply(lambda d: d["data"]["SOME_BACKEND_SECRET"])}",
    ],
)

frontend = docker.Container(
    "frontend",
    image="frontend:dev",
    build=docker.DockerBuildArgs(
        context=".",
        dockerfile="./docker/frontend/Dockerfile",
    ),
    depends_on=[backend],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=backend_network.name,
    )],
    command=["runner"],
    ports=[docker.ContainerPortArgs(
        internal=5173,
        external=5173,
    )],
)

prometheus = docker.Container(
    "prometheus",
    image="prom/prometheus:v3.1.0",
    restart="unless-stopped",
    volumes=[
        docker.ContainerVolumeArgs(
            host_path="./docker/prometheus/prometheus.yml",
            container_path="/etc/prometheus/prometheus.yml",
        ),
        docker.ContainerVolumeArgs(
            volume_name=volumes["prometheus_data"].name,
            container_path="/prometheus",
        ),
    ],
    depends_on=[backend],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=monitoring_network.name,
    )],
    ports=[docker.ContainerPortArgs(
        internal=9090,
        external=9090,
    )],
)

jaeger = docker.Container(
    "jaeger",
    image="jaegertracing/all-in-one:1.68.0",
    restart="unless-stopped",
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=monitoring_network.name,
    )],
    ports=[
        docker.ContainerPortArgs(internal=16686, external=16686),
        docker.ContainerPortArgs(internal=4317, external=4317),
        docker.ContainerPortArgs(internal=4318, external=4318),
    ],
)

grafana = docker.Container(
    "grafana",
    image="grafana/grafana:11.3.2",
    restart="unless-stopped",
    volumes=[
        docker.ContainerVolumeArgs(
            host_path="./docker/grafana/provisioning/",
            container_path="/etc/grafana/provisioning/",
        ),
        docker.ContainerVolumeArgs(
            volume_name=volumes["grafana_data"].name,
            container_path="/var/lib/grafana",
        ),
    ],
    depends_on=[prometheus],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=monitoring_network.name,
    )],
    ports=[docker.ContainerPortArgs(
        internal=3000,
        external=3000,
    )],
    envs=[
        f"GF_SECURITY_ADMIN_PASSWORD={grafana_secrets.data.apply(lambda d: d["data"]["GF_SECURITY_ADMIN_PASSWORD"])}",
        f"GF_USERS_ALLOW_SIGN_UP=false",
        "GF_SERVER_SERVE_FROM_SUB_PATH=true",
        "GF_SERVER_ROOT_URL=/monitoring",
    ],
)

minio = docker.Container(
    "minio",
    image="minio/minio",
    restart="unless-stopped",
    volumes=[docker.ContainerVolumeArgs(
        volume_name=volumes["minio_data"].name,
        container_path="/data",
    )],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=backend_network.name,
    )],
    command=["server /data --console-address :9001"],
    envs=[
        f"MINIO_ROOT_USER={os.getenv("MINIO_ROOT_USER", "minioadmin")}",
        f"MINIO_ROOT_PASSWORD={os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")}",
    ],
    ports=[docker.ContainerPortArgs(
        internal=9000,
        external=9000,
    )],
)

minio_provider = MinioProvider(
    "minio-provider",
    endpoint="localhost:9000",
    access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
    ssl=False,
)

materials_bucket = S3Bucket(
    "materials-bucket",
    bucket="materials",
    opts=pulumi.ResourceOptions(
        provider=minio_provider,
        depends_on=[minio],
    )
)

export("frontend_url", "http://localhost:5173")
export("backend_url", "http://localhost:8081")
export("grafana_url", "http://localhost:3000")
export("prometheus_url", "http://localhost:9090")
export("jaeger_url", "http://localhost:16686")
export("vault_url", f"http://localhost:{vault_port}")
export("minio_url", "http://localhost:9000")
export("minio_bucket_name", materials_bucket.bucket)