# sunbeam-ci
Continuous testing for Microstack/Sunbeam

Implements automation for deploying different scenarios through Jenkins.

Dependencies:
- terraform (from official repos)
- python3-paramiko (from standard ubuntu repos)
- mergedeep (from pip3 install)
- jq

# Usage
All commands are run from the sunbeam-ci directory.

## Setup
- `cp profiles.yaml.example profiles.yaml`
- edit profiles.yaml to match the environment
- Setup your deployment config: `export JENKINS_JSON_CONFIG='{ "profile": "maasdeployment", "channel": "2024.1/edge", "channelcp": "edge"}'`
  - profile: type of deployment to use (equinix, ob76, maasdeployment, felabdeployment, tokenlabs)
  - channel: snap channel to use
  - channelcp: risk level to use for control plane (stable, candidate, beta, edge)
- Setup your deployment credentials: `export JENKINS_JSON_CREDS='{ "api_key": "<MAAS_API_KEY>" }'`

## MAAS Deployment
This deployment type is useful for testing/demos of Sunbeam.

### Deploy
`./src/manage_substrate.py build`

`./src/deploy.py`

### Destroy
`./src/manage_substrate.py destroy`

## MAAS Manual Deployment
This deployment type is useful for CI.

- for maas nodes, it will look for tag 'jenkins'
