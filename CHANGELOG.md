# Changelog

## [0.1.8](https://github.com/rootcube/data-mesh-template/compare/v0.1.7...v0.1.8) (2026-09-25)


### Features

* add CI setup job for multi-OS support and update documentation ([a6ac223](https://github.com/rootcube/data-mesh-template/commit/a6ac223a08debb125a21f73056c872b3cce07f00))
* add CI setup job for multi-OS support and update documentation ([9c288cd](https://github.com/rootcube/data-mesh-template/commit/9c288cda89ec0b0cd6156f303128e5c3bea82fef))
* update sqlfluff commands to include config path for linting and fixing models ([141370a](https://github.com/rootcube/data-mesh-template/commit/141370a4b61ca381695637f32efbb9675cf2d354))


### Bug Fixes

* **dbt:** correct calendar dates, schema resolution and holiday config ([19a15b6](https://github.com/rootcube/data-mesh-template/commit/19a15b671f6bcde5029dd774783126ae7947ca90))
* **docs:** update Terraform commands to reflect changes in `just tf c… ([8d54b7c](https://github.com/rootcube/data-mesh-template/commit/8d54b7c6b70d217ad306829bb993db1f905aa616))
* **docs:** update Terraform commands to reflect changes in `just tf clean` ([23e892d](https://github.com/rootcube/data-mesh-template/commit/23e892d0389b8323312a927deb74664798f2a00c))
* **ingestion:** fail closed on a blank prefix and empty staging tables ([b09a3e5](https://github.com/rootcube/data-mesh-template/commit/b09a3e5b2128680a4830fd0883b796e2a1825074))
* **setup:** harden key-pair setup, bootstrap and .env writing ([f807113](https://github.com/rootcube/data-mesh-template/commit/f807113f13f870d4e523053ca284173258c11a81))
* **terraform:** tighten grants, protect databases and validate users ([0c260c4](https://github.com/rootcube/data-mesh-template/commit/0c260c4726fdf7c97dfd3a683683fa07ce449f47))
* **tooling:** run validate and the pre-commit hooks on Windows ([1479bb5](https://github.com/rootcube/data-mesh-template/commit/1479bb5d7a22702c07b8cfafdc5bcbecfc60b058))


### Documentation

* align the documentation with the audit fixes ([dadc78a](https://github.com/rootcube/data-mesh-template/commit/dadc78abfddc0ae175d61d8d768e0f3578765947))

## [0.1.7](https://github.com/rootcube/data-mesh-template/compare/v0.1.6...v0.1.7) (2026-09-25)


### Features

* remove unused weather measurement and observation YAML files ([dd1c6b2](https://github.com/rootcube/data-mesh-template/commit/dd1c6b2927ca19f4aea17572d9bcca3166af8299))
* remove unused weather measurement and observation YAML files ([ac01fc8](https://github.com/rootcube/data-mesh-template/commit/ac01fc8050a95b6454c045e572ec45f6589e46ca))

## [0.1.6](https://github.com/rootcube/data-mesh-template/compare/v0.1.5...v0.1.6) (2026-09-25)


### Features

* add personal schema prefix support and update related documenta… ([36200f1](https://github.com/rootcube/data-mesh-template/commit/36200f1605af0e3dba54b07dbd6c4f3796d4e70d))
* add personal schema prefix support and update related documentation ([eef641e](https://github.com/rootcube/data-mesh-template/commit/eef641e99d94f048bd6b49802a242412c7ef291e))

## [0.1.5](https://github.com/rootcube/data-mesh-template/compare/v0.1.4...v0.1.5) (2026-09-25)


### Features

* add KNMI weather data models and seeds for measurement types and stations ([8d02d2a](https://github.com/rootcube/data-mesh-template/commit/8d02d2a4dd7b97e3b0f70f098aeb40813489f16f))
* handle fresh install on Windows ([33ab62b](https://github.com/rootcube/data-mesh-template/commit/33ab62be6c392bf39abbfb5fe1fc1add50c13716))
* handle fresh install on Windows and improve setup wizard if account already exists (tf state sync/wipe options added). ([4f0fee8](https://github.com/rootcube/data-mesh-template/commit/4f0fee86ded5f36d69f9623738e0af0b83f54ed7))
* update dlt ingestion and dbt models for knmi ([10aaff6](https://github.com/rootcube/data-mesh-template/commit/10aaff680d637bd37db53c008c1e401db391b7bc))


### Bug Fixes

* update refresh_stages.sql to correct stage reference from ST_DLT to ST_DEFAULT ([f411bf9](https://github.com/rootcube/data-mesh-template/commit/f411bf9efb62b621119b4d9668f38e407f925497))
* update snowflake destination and load stage to include source-specific paths ([a9d6e74](https://github.com/rootcube/data-mesh-template/commit/a9d6e74132378bf0e1ae1b092b31aa2e921ff67f))

## [0.1.4](https://github.com/rootcube/data-mesh-template/compare/v0.1.3...v0.1.4) (2026-09-24)


### Bug Fixes

* update CI configuration and documentation references to use Zensical ([52bb01d](https://github.com/rootcube/data-mesh-template/commit/52bb01d91f367bd5ea68f6b4693b7c9261600a89))


### Documentation

* add note about Zensical template overrides in index.md ([fd01945](https://github.com/rootcube/data-mesh-template/commit/fd019452e77adcaada0a29ebe2e0d754c77c201c))

## [0.1.3](https://github.com/rootcube/data-mesh-template/compare/v0.1.2...v0.1.3) (2026-09-24)


### Features

* enhance setup instructions for clarity and usability, including Terraform installation guidance ([b7d73f2](https://github.com/rootcube/data-mesh-template/commit/b7d73f265ff5fa5b537f9e53750d021049174c6a))
* enhance user configuration handling with warnings for missing account logins ([e527773](https://github.com/rootcube/data-mesh-template/commit/e527773df165180968504ac6a7edca7f4e339ec9))
* implement staging tables in temporary layer for merge loads in … ([1212389](https://github.com/rootcube/data-mesh-template/commit/121238961c8cd0e7270b1fa3d24f66a331c5dc91))
* implement staging tables in temporary layer for merge loads in Snowflake ([14044ef](https://github.com/rootcube/data-mesh-template/commit/14044ef19dfed8947a549aa280aa74c0e882bca4))
* improve setup experience ([a4f2c87](https://github.com/rootcube/data-mesh-template/commit/a4f2c87d74a80d179dd33ddf0bdce4393f62174d))
* improve setup experience with clearer instructions and tool installation guidance ([8cb48df](https://github.com/rootcube/data-mesh-template/commit/8cb48df770d4dd4a971cb1d8fe0f0288b4fac08d))

## [0.1.2](https://github.com/rootcube/data-mesh-template/compare/v0.1.1...v0.1.2) (2026-09-24)


### Features

* setup dependabot ([ad9b719](https://github.com/rootcube/data-mesh-template/commit/ad9b7199db00d19db0e0efde35b77ca6d4e03773))

## [0.1.1](https://github.com/rootcube/data-mesh-template/compare/v0.1.0...v0.1.1) (2026-09-24)


### Features

* add initial project structure with configuration files and SQL macros ([b9d0cfe](https://github.com/rootcube/data-mesh-template/commit/b9d0cfee67d220fb178c3c064c6897c7896b5f48))
* add internal stage handling for dlt load files in Snowflake destination ([d5da71c](https://github.com/rootcube/data-mesh-template/commit/d5da71c05a154a4e5010d940edbde7a7a0c8d645))
* add internal stage handling for dlt load files in Snowflake destination ([8bf1173](https://github.com/rootcube/data-mesh-template/commit/8bf1173434e55c30c0d488ef1919e21a85bf3f30))
* add internal stage handling for dlt load files in Snowflake destination ([97a5568](https://github.com/rootcube/data-mesh-template/commit/97a556843306755f716b202f91f7951ceb10cb31))
* add refresh stages functionality to internal dlt load stage ([d4f191e](https://github.com/rootcube/data-mesh-template/commit/d4f191e489fcc646e279fbf9da5a2c3827df3d03))
* add release-please configuration and branch protection settings ([433ef0d](https://github.com/rootcube/data-mesh-template/commit/433ef0d72e9e74a64f780f5eecf19916d361dc00))
* enhance setup instructions and commands for clarity and usability ([305fab9](https://github.com/rootcube/data-mesh-template/commit/305fab97c9bf3ba03297dfa11c0e2a0d0c651929))
* initialize repository ([222d6c8](https://github.com/rootcube/data-mesh-template/commit/222d6c8be9e802fe4c311cf93c10dba363f4b119))
* introduce common models for environment, time, and holiday dimensions ([dd74741](https://github.com/rootcube/data-mesh-template/commit/dd747410c068e62d9c7ed042a85843e4f4a01929))
* merge init repo ([222d6c8](https://github.com/rootcube/data-mesh-template/commit/222d6c8be9e802fe4c311cf93c10dba363f4b119))


### Bug Fixes

* add .tfplan to .gitignore ([d9ee4d6](https://github.com/rootcube/data-mesh-template/commit/d9ee4d635fbb724bcc5bdc1fdd408d1883182354))
* update asset key and group naming conventions in documentation and configuration ([7d6e516](https://github.com/rootcube/data-mesh-template/commit/7d6e516de4cbfec4859e98e63bbd511c40ab5fc2))
* update documentation to replace 'just snowflake' with 'just sf' ([2ec5240](https://github.com/rootcube/data-mesh-template/commit/2ec52404a79a5343640059a75f0d967d76cb2e54))
* update repository references from enexis-dev-day to data-mesh-template ([b00d8b1](https://github.com/rootcube/data-mesh-template/commit/b00d8b1856f61ee7437348f0bdb8485f81e3925b))
* update Snowflake bootstrap instructions to separate organization and account name ([91253e6](https://github.com/rootcube/data-mesh-template/commit/91253e6ac614717456fe095abc13675df41304bf))
* update troubleshooting instructions and .venv handling in justfile ([535af9f](https://github.com/rootcube/data-mesh-template/commit/535af9f2551a2928fd8b6ec463dd7263ac6294ab))
* update user references to use 'username@example.com' in documentation and configuration ([aed333f](https://github.com/rootcube/data-mesh-template/commit/aed333fad2aca127ca88c2f42911977027afe01d))


### Documentation

* update git workflow documentation for release-please integration ([481658f](https://github.com/rootcube/data-mesh-template/commit/481658f716a2f9f65dae19306c7a8b3ea6413369))
* update installation instructions for optional tools in documentation ([2e54bce](https://github.com/rootcube/data-mesh-template/commit/2e54bce392cff6e44ce2140d18eb30451c970e04))
