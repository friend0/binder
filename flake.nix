{
  description = "Hashed MTG binder organizer";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            # stdlib only today; add Python packages here, e.g. ps.requests for Scryfall
            (pkgs.python312.withPackages (ps: [ ]))
            pkgs.nodejs # check_web.py runs docs/binder.js
          ];
          shellHook = ''
            export PYTHONDONTWRITEBYTECODE=1
            echo "binder dev shell: $(python3 --version)  (try: python3 binder.py where 'Sol Ring')"
          '';
        };
      });
    };
}
