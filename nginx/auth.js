var crypto = require('crypto');

const SECRET = Buffer.from( process.env.SIGNING_SECRET, "utf8" );

function base64url(buffer) {
    return buffer
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
}

function validate(r) {
    const sig = r.variables.original_sig;
    const expires = r.variables.original_expires;
    const requestUri = r.variables.original_uri;

    r.error(`auth: request_uri=${requestUri}`);
    r.error(`auth: sig=${sig}`);
    r.error(`auth: expires=${expires}`);

    if (!sig || !expires) {
        r.return(403, "Missing signature");
        return;
    }

    const expiresInt = parseInt(expires, 10);

    if (Number.isNaN(expiresInt)) {
        r.return(403, "Bad expires");
        return;
    }

    const now = Math.floor(Date.now() / 1000);

    if (now > expiresInt) {
        r.return(403, "URL expired");
        return;
    }

    const payload = `${requestUri}:${expiresInt}`;

    r.error(`auth: payload=${payload}`);

    const digest = crypto
        .createHmac('md5', SECRET)
        .update(Buffer.from(payload, 'utf8'))
        .digest();

    const expectedSig = base64url(digest);

    r.error(`auth: expectedSig=${expectedSig}`);

    if (sig !== expectedSig) {
        r.return(403, "Bad signature");
        return;
    }

    r.return(204);
}

export default { validate };