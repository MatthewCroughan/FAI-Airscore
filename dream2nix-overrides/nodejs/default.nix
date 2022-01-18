{
  lib,
  pkgs,

  # dream2nix
  satisfiesSemver,
  ...
}: 
let
  myPython = 
    (python39.withPackages (p: [ 
      p.flask
      p.flask_static_digest
      p.setuptools
      p.flask_wtf
      p.flask_login
      p.flask_debugtoolbar
      p.flask_bcrypt
      p.flask_migrate
      p.flask_mail
      p.flask-caching
      p.requests
      p.ruamel-base
      p.ruamel-yaml
      p.environs
      p.pymysql
      p.folium
      p.geographiclib
      p.geopy
      p.pyproj
      p.pyjwt
    ]));
  python39Packages = python39.pkgs;
  python39 = pkgs.python39.override {
    packageOverrides = self: super: {
      flask = super.flask.overridePythonAttrs (old: {
        propagatedBuildInputs = old.propagatedBuildInputs ++ [ self.flask_static_digest ];
        pythonImportsCheck = [ "flask_static_digest" ];
        pythonPath = [ self.flask_static_digest ];
      });
      flask_debugtoolbar = self.buildPythonPackage rec {
        pname = "Flask-DebugToolbar";
        version = "0.11.0";
        propagatedBuildInputs = [ self.flask self.blinker ];
        doCheck = false;
        src = self.fetchPypi {
          inherit pname version;
          sha256 = "sha256-PE5501Tt4BTmZXxUWlNtT7JzzInj/WtINbAuNG3TqrQ=";
        };
      };
      flask_bcrypt = self.buildPythonPackage rec {
        pname = "Flask-Bcrypt";
        version = "0.7.1";
        propagatedBuildInputs = [ self.bcrypt super.flask ];
        doCheck = false;
        src = self.fetchPypi {
          inherit pname version;
          sha256 = "sha256-1xyFhbLuHGICQ5Lr28RHQ4Vk4sjAK05XtWpMr9jRPF8=";
        };
      };
      flask_static_digest = self.buildPythonPackage rec {
        pname = "Flask-Static-Digest";
        version = "0.2.1";
        propagatedBuildInputs = [ super.flask ];
        src = self.fetchPypi {
          inherit pname version;
          sha256 = "sha256-dSiwiiwS3DqCgJa2buJhLzI9UL420B8oF7dn+7HOym4=";
        };
      };
    };
  };
#  flask_withStaticDigest = pkgs.symlinkJoin {
#    name = "flask_withStaticDigest";
#    nativeBuildInputs = [ pkgs.makeWrapper ];
#    paths = [ pkgs.python38Packages.flask ];
#    postBuild = ''
#      wrapProgram $out/bin/flask \
#        --prefix PATH: "${flask_static_digest}"
#    '';
#  };
#  flask_withStaticDigest = pkgs.python38Packages.flask.overrideAttrs {
#    name = "flask_withStaticDigest";
#    nativeBuildInputs = [ pkgs.makeWrapper ];
#    paths = [ pkgs.python38Packages.flask ];
#    postBuild = ''
#      wrapProgram $out/bin/flask \
#        --prefix PATH: "${flask_static_digest}"
#    '';
#  };
#  flask_withStaticDigest = pkgs.python38Packages.flask.overridePythonAttrs (old: {
#    buildInputs = [ flask_static_digest ];
#  });
#  myPython = pkgs.python38.withPackages (_: [ flask_withStaticDigest ]);
in
{
  airscore.build = {
    preBuild = ''
      export FLASK_APP=autoapp.py FLASK_ENV=production
      export PYTHONPATH=''${PYTHONPATH}:$src/airscore/core
      echo $PYTHONPATH
      mv defines.yaml.example defines.yaml
      mv .env.example .env
      source .env
      ls $src/airscore/core
      python autoapp.py
    '';
    nativeBuildInputs = old: old ++ [
      myPython
      #python39Packages.flask
    ];
  };
}

