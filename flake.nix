{
  description = "Chessnut Move driver + server + client";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonBase = pkgs.python312;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonBase
            git
          ];

          shellHook = ''
            if [ ! -d .venv ]; then
              echo "Creating Python virtual environment..."
              python -m venv .venv
            fi

            source .venv/bin/activate

            if [ -f requirements.txt ]; then
              if [ ! -f .venv/.requirements-installed ] || [ requirements.txt -nt .venv/.requirements-installed ]; then
                echo "Installing Python dependencies..."
                pip install -q -r requirements.txt
                touch .venv/.requirements-installed
              fi
            fi

            echo ""
            echo "Chessnut Move Stack"
            echo "Python: $(python --version)"
            echo "Venv:   .venv (activated)"
            echo ""
          '';
        };
      });
}
