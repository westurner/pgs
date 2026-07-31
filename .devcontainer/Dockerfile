# Dev container Dockerfile for the pgs project
# Configures a rootless environment based on Fedora Toolbox 44
FROM quay.io/fedora/fedora-toolbox:44

LABEL org.opencontainers.image.title="pgs-devcontainer"
LABEL org.opencontainers.image.description="Development container for the pgs project"
LABEL org.opencontainers.image.authors="pgs contributors"

# Create the vscode user and give them passwordless sudo
RUN useradd -m -s /bin/bash vscode \
    && usermod -aG wheel vscode \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

# Install standard Python development tools and project requirements
RUN dnf install -y \
    python3 \
    python3-pip \
    python3-virtualenv \
    git \
    make \
    \
    findutils \
    ripgrep \
    jq \
    curl \
    wget \
    tar \
    unzip \
    bash-completion \
    python3-argcomplete \
    \
    && dnf clean all

# Set the default user
USER vscode

# Set the working directory
WORKDIR /workspace

