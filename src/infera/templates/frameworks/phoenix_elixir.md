# Phoenix (Elixir) on Fly.io / Cloud Run

## Overview

Deploy Phoenix applications on Fly.io or Cloud Run for highly concurrent, fault-tolerant web applications. Phoenix leverages the Erlang VM (BEAM) for exceptional concurrency handling, real-time features with LiveView, and distributed systems capabilities. Ideal for applications requiring WebSockets, real-time updates, and high availability.

## Detection Signals

Use this template when:
- `mix.exs` with `:phoenix` dependency
- `lib/*/endpoint.ex` exists
- `config/config.exs` with Phoenix configuration
- `router.ex` with Phoenix.Router
- Real-time features needed (LiveView)
- High concurrency required
- WebSocket connections
- Distributed systems

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Deployment Platform                           │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Edge / Load Balancer                    │   │
                    │   │              (Fly Edge / Cloud Load Balancer)            │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              BEAM Instances (Fly Machines / Cloud Run)  │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │  Phoenix  │ │  Phoenix  │ │  Phoenix  │             │   │
                    │   │  │ + BEAM    │ │ + BEAM    │ │ + BEAM    │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │ LiveView  │◄─►LiveView  │◄─►LiveView  │             │   │
                    │   │  │ Channels  │ │ Channels  │ │ Channels  │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │         ▲               ▲               ▲               │   │
                    │   │         └───────────────┼───────────────┘               │   │
                    │   │              Distributed Erlang Clustering               │   │
                    │   │                                                         │   │
                    │   │  Millions of connections • <10ms latency • Auto-healing │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │ PostgreSQL│     │   Redis   │     │  Storage  │            │
                    │   │(Fly/Cloud │     │  (PubSub) │     │(Tigris/S3)│            │
                    │   │   SQL)    │     │           │     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Real-time • Fault-tolerant • Hot upgrades • Distributed      │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Fly.io (Recommended)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Fly Machines | BEAM VMs | shared-cpu-2x |
| Fly Postgres | Database | 1GB RAM |
| Upstash Redis | PubSub | 100MB |
| Tigris | Object storage | S3-compatible |

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container | 2 vCPU, 2GB RAM |
| Cloud SQL | PostgreSQL | db-f1-micro |
| Memorystore | Redis PubSub | 1GB |
| Cloud Storage | File uploads | Regional |

## Configuration

### Project Structure
```
my_phoenix_app/
├── lib/
│   ├── my_app/                    # Business logic
│   │   ├── application.ex         # OTP Application
│   │   ├── repo.ex               # Ecto Repo
│   │   └── accounts/             # Context
│   │       ├── user.ex
│   │       └── accounts.ex
│   ├── my_app_web/               # Web layer
│   │   ├── endpoint.ex
│   │   ├── router.ex
│   │   ├── controllers/
│   │   ├── live/
│   │   │   └── user_live/
│   │   ├── components/
│   │   └── telemetry.ex
│   └── my_app_web.ex
├── priv/
│   └── repo/
│       └── migrations/
├── config/
│   ├── config.exs
│   ├── dev.exs
│   ├── prod.exs
│   └── runtime.exs
├── mix.exs
├── mix.lock
├── Dockerfile
├── fly.toml
└── rel/
    └── overlays/
```

### mix.exs
```elixir
defmodule MyApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :my_app,
      version: "0.1.0",
      elixir: "~> 1.16",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps()
    ]
  end

  def application do
    [
      mod: {MyApp.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  defp deps do
    [
      # Phoenix
      {:phoenix, "~> 1.7.10"},
      {:phoenix_html, "~> 4.0"},
      {:phoenix_live_reload, "~> 1.4", only: :dev},
      {:phoenix_live_view, "~> 0.20"},
      {:phoenix_live_dashboard, "~> 0.8"},

      # Database
      {:phoenix_ecto, "~> 4.4"},
      {:ecto_sql, "~> 3.11"},
      {:postgrex, ">= 0.0.0"},

      # Assets
      {:esbuild, "~> 0.8", runtime: Mix.env() == :dev},
      {:tailwind, "~> 0.2", runtime: Mix.env() == :dev},

      # PubSub
      {:phoenix_pubsub, "~> 2.1"},
      {:phoenix_pubsub_redis, "~> 3.0"},

      # Auth
      {:bcrypt_elixir, "~> 3.1"},

      # HTTP Client
      {:finch, "~> 0.18"},
      {:req, "~> 0.4"},

      # JSON
      {:jason, "~> 1.4"},

      # Telemetry
      {:telemetry_metrics, "~> 0.6"},
      {:telemetry_poller, "~> 1.0"},

      # Distributed
      {:libcluster, "~> 3.3"},
      {:dns_cluster, "~> 0.1"},

      # Storage
      {:ex_aws, "~> 2.5"},
      {:ex_aws_s3, "~> 2.5"},

      # Server
      {:plug_cowboy, "~> 2.6"},
      {:bandit, "~> 1.2"}
    ]
  end

  defp aliases do
    [
      setup: ["deps.get", "ecto.setup", "assets.setup", "assets.build"],
      "ecto.setup": ["ecto.create", "ecto.migrate", "run priv/repo/seeds.exs"],
      "ecto.reset": ["ecto.drop", "ecto.setup"],
      test: ["ecto.create --quiet", "ecto.migrate --quiet", "test"],
      "assets.setup": ["tailwind.install --if-missing", "esbuild.install --if-missing"],
      "assets.build": ["tailwind my_app", "esbuild my_app"],
      "assets.deploy": [
        "tailwind my_app --minify",
        "esbuild my_app --minify",
        "phx.digest"
      ]
    ]
  end
end
```

### Runtime Configuration
```elixir
# config/runtime.exs
import Config

if System.get_env("PHX_SERVER") do
  config :my_app, MyAppWeb.Endpoint, server: true
end

if config_env() == :prod do
  database_url =
    System.get_env("DATABASE_URL") ||
      raise """
      environment variable DATABASE_URL is missing.
      For example: ecto://USER:PASS@HOST/DATABASE
      """

  maybe_ipv6 = if System.get_env("ECTO_IPV6") in ~w(true 1), do: [:inet6], else: []

  config :my_app, MyApp.Repo,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
    socket_options: maybe_ipv6,
    ssl: true

  # Redis PubSub
  redis_url = System.get_env("REDIS_URL")
  if redis_url do
    config :my_app, MyAppWeb.Endpoint,
      pubsub_server: MyApp.PubSub,
      pubsub: [
        adapter: Phoenix.PubSub.Redis,
        url: redis_url,
        node_name: System.get_env("FLY_ALLOC_ID") || node()
      ]
  end

  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      You can generate one by calling: mix phx.gen.secret
      """

  host = System.get_env("PHX_HOST") || "example.com"
  port = String.to_integer(System.get_env("PORT") || "4000")

  config :my_app, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")

  config :my_app, MyAppWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [
      ip: {0, 0, 0, 0, 0, 0, 0, 0},
      port: port
    ],
    secret_key_base: secret_key_base
end
```

### Application Supervisor
```elixir
# lib/my_app/application.ex
defmodule MyApp.Application do
  @moduledoc false
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      MyAppWeb.Telemetry,
      MyApp.Repo,
      {DNSCluster, query: Application.get_env(:my_app, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: MyApp.PubSub},
      {Finch, name: MyApp.Finch},
      MyAppWeb.Endpoint
    ]

    opts = [strategy: :one_for_one, name: MyApp.Supervisor]
    Supervisor.start_link(children, opts)
  end

  @impl true
  def config_change(changed, _new, removed) do
    MyAppWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
```

### User Context
```elixir
# lib/my_app/accounts/accounts.ex
defmodule MyApp.Accounts do
  import Ecto.Query, warn: false
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def list_users(opts \\ []) do
    limit = Keyword.get(opts, :limit, 20)
    offset = Keyword.get(opts, :offset, 0)

    query =
      from u in User,
        where: u.is_active == true,
        order_by: [desc: u.inserted_at],
        limit: ^limit,
        offset: ^offset

    users = Repo.all(query)
    total = Repo.aggregate(from(u in User, where: u.is_active == true), :count)

    {users, total}
  end

  def get_user!(id), do: Repo.get!(User, id)

  def get_user_by_email(email) do
    Repo.get_by(User, email: email)
  end

  def create_user(attrs \\ %{}) do
    %User{}
    |> User.changeset(attrs)
    |> Repo.insert()
  end

  def update_user(%User{} = user, attrs) do
    user
    |> User.changeset(attrs)
    |> Repo.update()
  end

  def delete_user(%User{} = user) do
    Repo.delete(user)
  end
end
```

### User Schema
```elixir
# lib/my_app/accounts/user.ex
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id
  schema "users" do
    field :email, :string
    field :name, :string
    field :password, :string, virtual: true, redact: true
    field :hashed_password, :string, redact: true
    field :is_active, :boolean, default: true

    timestamps(type: :utc_datetime)
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :password])
    |> validate_required([:email, :name])
    |> validate_email()
    |> validate_password()
  end

  defp validate_email(changeset) do
    changeset
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/, message: "must have @ sign and no spaces")
    |> validate_length(:email, max: 160)
    |> unsafe_validate_unique(:email, MyApp.Repo)
    |> unique_constraint(:email)
  end

  defp validate_password(changeset) do
    changeset
    |> validate_length(:password, min: 8, max: 72)
    |> hash_password()
  end

  defp hash_password(changeset) do
    password = get_change(changeset, :password)

    if password && changeset.valid? do
      changeset
      |> delete_change(:password)
      |> put_change(:hashed_password, Bcrypt.hash_pwd_salt(password))
    else
      changeset
    end
  end
end
```

### LiveView Component
```elixir
# lib/my_app_web/live/user_live/index.ex
defmodule MyAppWeb.UserLive.Index do
  use MyAppWeb, :live_view

  alias MyApp.Accounts
  alias MyApp.Accounts.User

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, "users")
    end

    {users, total} = Accounts.list_users(limit: 20, offset: 0)

    {:ok,
     socket
     |> assign(:page_title, "Users")
     |> stream(:users, users)
     |> assign(:total, total)
     |> assign(:page, 1)}
  end

  @impl true
  def handle_params(params, _url, socket) do
    {:noreply, apply_action(socket, socket.assigns.live_action, params)}
  end

  defp apply_action(socket, :index, _params) do
    socket
    |> assign(:page_title, "Listing Users")
    |> assign(:user, nil)
  end

  defp apply_action(socket, :new, _params) do
    socket
    |> assign(:page_title, "New User")
    |> assign(:user, %User{})
  end

  @impl true
  def handle_info({MyAppWeb.UserLive.FormComponent, {:saved, user}}, socket) do
    {:noreply, stream_insert(socket, :users, user)}
  end

  @impl true
  def handle_info({:user_created, user}, socket) do
    {:noreply, stream_insert(socket, :users, user, at: 0)}
  end

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    user = Accounts.get_user!(id)
    {:ok, _} = Accounts.delete_user(user)

    {:noreply, stream_delete(socket, :users, user)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <.header>
      Users
      <:actions>
        <.link patch={~p"/users/new"}>
          <.button>New User</.button>
        </.link>
      </:actions>
    </.header>

    <.table
      id="users"
      rows={@streams.users}
      row_click={fn {_id, user} -> JS.navigate(~p"/users/#{user}") end}
    >
      <:col :let={{_id, user}} label="Email"><%= user.email %></:col>
      <:col :let={{_id, user}} label="Name"><%= user.name %></:col>
      <:action :let={{_id, user}}>
        <.link navigate={~p"/users/#{user}"}>Show</.link>
      </:action>
      <:action :let={{id, user}}>
        <.link
          phx-click={JS.push("delete", value: %{id: user.id}) |> hide("##{id}")}
          data-confirm="Are you sure?"
        >
          Delete
        </.link>
      </:action>
    </.table>

    <.modal :if={@live_action in [:new, :edit]} id="user-modal" show on_cancel={JS.patch(~p"/users")}>
      <.live_component
        module={MyAppWeb.UserLive.FormComponent}
        id={@user.id || :new}
        title={@page_title}
        action={@live_action}
        user={@user}
        patch={~p"/users"}
      />
    </.modal>
    """
  end
end
```

### Health Check Controller
```elixir
# lib/my_app_web/controllers/health_controller.ex
defmodule MyAppWeb.HealthController do
  use MyAppWeb, :controller

  def index(conn, _params) do
    health = %{
      status: "healthy",
      database: check_database(),
      node: node(),
      nodes: Node.list()
    }

    status = if health.database == :ok, do: 200, else: 503

    conn
    |> put_status(status)
    |> json(health)
  end

  defp check_database do
    try do
      MyApp.Repo.query!("SELECT 1")
      :ok
    rescue
      _ -> :error
    end
  end
end
```

### Dockerfile
```dockerfile
# Build stage
ARG ELIXIR_VERSION=1.16.0
ARG OTP_VERSION=26.2.1
ARG DEBIAN_VERSION=bookworm-20231009-slim

ARG BUILDER_IMAGE="hexpm/elixir:${ELIXIR_VERSION}-erlang-${OTP_VERSION}-debian-${DEBIAN_VERSION}"
ARG RUNNER_IMAGE="debian:${DEBIAN_VERSION}"

FROM ${BUILDER_IMAGE} as builder

# Install build dependencies
RUN apt-get update -y && apt-get install -y build-essential git \
    && apt-get clean && rm -f /var/lib/apt/lists/*_*

WORKDIR /app

# Install hex + rebar
RUN mix local.hex --force && \
    mix local.rebar --force

ENV MIX_ENV="prod"

# Install dependencies
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV
RUN mkdir config

# Copy config
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

# Copy source
COPY priv priv
COPY lib lib
COPY assets assets

# Compile assets
RUN mix assets.deploy

# Compile application
RUN mix compile

# Copy runtime config
COPY config/runtime.exs config/

# Build release
COPY rel rel
RUN mix release

# Runtime stage
FROM ${RUNNER_IMAGE}

RUN apt-get update -y && \
  apt-get install -y libstdc++6 openssl libncurses5 locales ca-certificates \
  && apt-get clean && rm -f /var/lib/apt/lists/*_*

# Set locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR "/app"
RUN chown nobody /app

ENV MIX_ENV="prod"

# Copy release
COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/my_app ./

USER nobody

CMD ["/app/bin/server"]
```

### fly.toml
```toml
app = "my-phoenix-app"
primary_region = "iad"
kill_signal = "SIGTERM"
kill_timeout = "5s"

[build]

[deploy]
  release_command = "/app/bin/migrate"

[env]
  PHX_HOST = "my-phoenix-app.fly.dev"
  PORT = "4000"

[http_service]
  internal_port = 4000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 2
  processes = ["app"]

  [http_service.concurrency]
    type = "connections"
    hard_limit = 10000
    soft_limit = 8000

[[services]]
  protocol = "tcp"
  internal_port = 4000
  processes = ["app"]

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    grace_period = "10s"
    method = "GET"
    path = "/health"

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 2
```

## Deployment Commands

### Fly.io
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch new app
fly launch

# Deploy
fly deploy

# Run migrations
fly ssh console -C "/app/bin/migrate"

# Open IEx console
fly ssh console -C "/app/bin/my_app remote"

# View logs
fly logs

# Scale
fly scale count 3

# Create Postgres
fly postgres create

# Attach database
fly postgres attach my-phoenix-app-db

# Create Upstash Redis
fly redis create
```

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT_ID}/phoenix-app

# Deploy
gcloud run deploy phoenix-app \
  --image gcr.io/${PROJECT_ID}/phoenix-app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 2 \
  --set-env-vars "PHX_SERVER=true,PHX_HOST=phoenix-app.run.app" \
  --set-secrets "DATABASE_URL=database-url:latest,SECRET_KEY_BASE=secret-key:latest"
```

## Cost Breakdown

### Fly.io
| Component | Monthly Cost |
|-----------|--------------|
| Machines (2x shared-cpu-2x) | ~$15 |
| Postgres (1GB) | ~$7 |
| Upstash Redis | ~$5 |
| **Total** | **~$27** |

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (2 min instances) | ~$60 |
| Cloud SQL | ~$25 |
| Memorystore | ~$35 |
| **Total** | **~$120** |

## Best Practices

1. **Use LiveView** - Server-rendered real-time UI
2. **PubSub for clustering** - Redis for multi-node PubSub
3. **DNS clustering** - Auto-discover nodes on Fly
4. **Proper health checks** - Verify database connectivity
5. **Release builds** - Use mix release for production
6. **Graceful shutdown** - Handle SIGTERM properly
7. **Telemetry** - Monitor with LiveDashboard
8. **Connection pooling** - Configure Ecto pool size

## Common Mistakes

1. **No clustering setup** - Nodes can't communicate
2. **Missing PubSub** - LiveView won't work across nodes
3. **Wrong health check** - Should verify dependencies
4. **No release migrations** - Migrations not running
5. **Small pool size** - Database connection exhaustion
6. **No SSL for database** - Security vulnerability
7. **Missing SECRET_KEY_BASE** - App won't start
8. **Wrong PHX_HOST** - Asset URLs broken

## Example Configuration

```yaml
# infera.yaml
project_name: my-phoenix-app
provider: fly

framework:
  name: phoenix
  version: "1.7"
  elixir_version: "1.16"

deployment:
  type: container

  machines:
    cpu: shared-cpu-2x
    memory: 512mb
    count: 2

  health_check:
    path: /health
    interval: 10s

database:
  type: postgresql
  provider: fly-postgres
  size: 1gb

cache:
  type: redis
  provider: upstash

env_vars:
  PHX_HOST: my-phoenix-app.fly.dev

secrets:
  - DATABASE_URL
  - SECRET_KEY_BASE
  - REDIS_URL
```

## Sources

- [Phoenix Documentation](https://hexdocs.pm/phoenix/overview.html)
- [Fly.io Phoenix Guide](https://fly.io/docs/elixir/getting-started/)
- [Phoenix Deployment](https://hexdocs.pm/phoenix/deployment.html)
- [LiveView Documentation](https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html)
