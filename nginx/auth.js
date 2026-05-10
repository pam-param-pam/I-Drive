var crypto = require('crypto');

const SECRET = Buffer.from("super-secret", "utf8");

function base64url(buffer) {
    return buffer
        .toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
}

function validate(r) {
    const sig = r.args.sig;
    const expires = r.args.expires;

    r.log(`auth: uri=${r.uri}`);
    r.log(`auth: sig=${sig}`);
    r.log(`auth: expires=${expires}`);

    if (!sig || !expires) {
        r.error("auth: missing signature params");

        r.return(403, "Missing signature");

        return;
    }

    const expiresInt = parseInt(expires, 10);

    if (Number.isNaN(expiresInt)) {
        r.error(`auth: invalid expires=${expires}`);

        r.return(403, "Bad expires");

        return;
    }

    const now = Math.floor(Date.now() / 1000);

    r.log(`auth: now=${now}`);

    if (now > expiresInt) {
        r.error(`auth: expired now=${now} expires=${expiresInt}`);

        r.return(403, "URL expired");

        return;
    }

    const payload = `${r.uri}:${expiresInt}`;

    r.log(`auth: payload=${payload}`);

    const digest = crypto
        .createHmac('md5', SECRET)
        .update(Buffer.from(payload, 'utf8'))
        .digest();

    const expectedSig = base64url(digest);

    r.log(`auth: expectedSig=${expectedSig}`);

    if (sig !== expectedSig) {
        r.error(
            `auth: signature mismatch provided=${sig} expected=${expectedSig}`
        );

        r.return(403, "Bad signature");

        return;
    }

    r.log("auth: signature valid");

    r.return(204);
}

export default { validate };