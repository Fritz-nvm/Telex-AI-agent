# FastAPI Country LLM

This project is a FastAPI application that integrates a large language model (LLM) to provide facts and cultural information about different countries. 

## Features

- Retrieve facts about various countries.
- Get cultural information and insights.
- RESTful API design for easy integration.

## Project Structure

```
fastapi-country-llm
├── app
│   ├── main.py                # Entry point of the FastAPI application
│   ├── api                    # API related files
│   │   ├── __init__.py
│   │   ├── deps.py            # Dependency functions for API routes
│   │   └── v1                 # Version 1 of the API
│   │       ├── __init__.py
│   │       └── countries.py    # API endpoints for country information
│   ├── core                   # Core application logic
│   │   ├── config.py          # Configuration settings
│   │   └── llm_client.py      # LLM integration
│   ├── services               # Business logic
│   │   └── country_service.py  # Country-related services
│   ├── models                 # Data models
│   │   └── country.py         # Country data model
│   ├── schemas                # Request and response schemas
│   │   └── country.py         # Country schemas
│   └── utils                  # Utility functions
│       └── country_data.py    # Functions for processing country data
├── tests                      # Test suite
│   ├── __init__.py
│   └── test_countries.py      # Unit tests for country API
├── requirements.txt           # Project dependencies
├── pyproject.toml            # Project metadata
├── Dockerfile                 # Docker image instructions
├── .env.example               # Example environment variables
└── README.md                  # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/fastapi-country-llm.git
   cd fastapi-country-llm
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the FastAPI application, execute the following command:

```
uvicorn app.main:app --reload
```

You can access the API documentation at `http://127.0.0.1:8000/docs`.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.