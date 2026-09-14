After logging in to admin home, we get back json with the following format:

{"access_token":"token","token_type":"bearer","expires_in_seconds":3600}

This needs to be attached to every subsequent request as a header, like this:

"Authorization: Bearer token"
