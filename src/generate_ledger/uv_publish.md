UV_PUBLISH_TOKEN="pypi-AgENdGVzdC5weXBpLm9yZwIkY2JhODM3YTctNjM5ZC00ZTZmLTg2YTAtMDVjY2FjMDYxZGE3AAIqWzMsIjc1NmExNmQwLWE0ZDQtNDRkMi05OGEwLTA0ZjE2ZTFkY2ZhMSJdAAAGIPq9mV2m5lHN1RwkD3LDEM9ZS_84ZApSlLwaCAsTFAoI"


Now when installing my package from the test.pypi, it should look on the _real_ pypi for dependencies:
    
pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple \
    generate-ledger
