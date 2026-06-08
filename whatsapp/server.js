const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const crypto = require('crypto');
const { execSync } = require('child_process');
const path = require('path');

// --- Shared-secret auth (SECURITY: fix for finding H7) ---
// Refuse to start without a token rather than auto-generating a weak one.
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
if (!WHATSAPP_TOKEN) {
    console.error(
        'FATAL: WHATSAPP_TOKEN is not set. Refusing to start the WhatsApp HTTP API ' +
        'because its routes can send messages and read contacts as you. ' +
        'Set WHATSAPP_TOKEN in the environment (e.g. in .env) and restart.'
    );
    process.exit(1);
}
const TOKEN_BUF = Buffer.from(WHATSAPP_TOKEN);

// Constant-time comparison of the provided header against the secret.
function tokenMatches(provided) {
    if (typeof provided !== 'string' || provided.length === 0) return false;
    const providedBuf = Buffer.from(provided);
    if (providedBuf.length !== TOKEN_BUF.length) return false;
    return crypto.timingSafeEqual(providedBuf, TOKEN_BUF);
}

const app = express();
app.use(express.json());

// Reject any request without a valid x-whatsapp-token header.
app.use((req, res, next) => {
    if (!tokenMatches(req.get('x-whatsapp-token'))) {
        return res.status(401).json({ ok: false, error: 'Unauthorized' });
    }
    next();
});

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
    // SECURITY: --no-sandbox / --disable-setuid-sandbox were removed. They disable the
    // Chromium renderer sandbox, so a compromised page rendered by Puppeteer (e.g. a
    // malicious link/preview in a WhatsApp message) could escape into the host process.
    // If WhatsApp Web fails to launch on a hardened/rootless environment that genuinely
    // requires these flags, re-add them ONLY as a last resort and document why here.
    puppeteer: {}
});

let isReady = false;

client.on('qr', (qr) => {
    console.log('\n📱 Scan this QR code with WhatsApp:\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    isReady = true;
    console.log('✅ WhatsApp connected. JARVIS is online.');
});

client.on('disconnected', () => {
    isReady = false;
    console.log('WhatsApp disconnected.');
});

client.on('message', async (msg) => {
    if (msg.fromMe) return;

    const contact = await msg.getContact();
    const sender = contact.pushname || contact.number || msg.from;
    const text = msg.body;

    console.log(`WhatsApp from ${sender}: ${text}`);

    // Route through JARVIS brain
    try {
        const response = await fetch('http://127.0.0.1:8080/api/whatsapp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-whatsapp-token': process.env.WHATSAPP_TOKEN || '' },
            body: JSON.stringify({ message: text, sender: sender, from: msg.from })
        });
        const data = await response.json();
        if (data.response) {
            await msg.reply(data.response);
        }
    } catch (e) {
        // Flask not running — respond directly via Python
        try {
            const jarvisPath = path.join(__dirname, '..', 'venv', 'bin', 'python3');
            const scriptPath = path.join(__dirname, 'reply.py');
            const result = execSync(
                `"${jarvisPath}" "${scriptPath}" "${text.replace(/"/g, '\\"')}"`,
                { timeout: 30000 }
            ).toString().trim();
            if (result) await msg.reply(result);
        } catch (err) {
            console.error('JARVIS reply error:', err.message);
        }
    }
});

// HTTP API for Python to send WhatsApp messages
app.post('/send', async (req, res) => {
    const { to, message } = req.body;
    if (!isReady) return res.json({ ok: false, error: 'Not connected' });
    try {
        const chatId = to.includes('@') ? to : `${to.replace(/\D/g, '')}@c.us`;
        await client.sendMessage(chatId, message);
        res.json({ ok: true });
    } catch (e) {
        res.json({ ok: false, error: e.message });
    }
});

// Send by contact name
app.post('/send-by-name', async (req, res) => {
    const { name, message } = req.body;
    if (!isReady) return res.json({ ok: false, error: 'Not connected' });
    try {
        const contacts = await client.getContacts();
        const needle = name.toLowerCase();
        const match = contacts.find(c =>
            (c.name || '').toLowerCase().includes(needle) ||
            (c.pushname || '').toLowerCase().includes(needle) ||
            (c.shortName || '').toLowerCase().includes(needle)
        );
        if (!match) return res.json({ ok: false, error: `Contact '${name}' not found` });
        await client.sendMessage(match.id._serialized, message);
        res.json({ ok: true, sent_to: match.name || match.pushname });
    } catch (e) {
        res.json({ ok: false, error: e.message });
    }
});

// Search contacts
app.get('/contacts', async (req, res) => {
    if (!isReady) return res.json({ ok: false, error: 'Not connected' });
    const query = (req.query.q || '').toLowerCase();
    try {
        const contacts = await client.getContacts();
        const results = contacts
            .filter(c => c.isMyContact && c.name)
            .filter(c => !query || (c.name || '').toLowerCase().includes(query))
            .slice(0, 20)
            .map(c => ({ name: c.name, number: c.number }));
        res.json({ ok: true, contacts: results });
    } catch (e) {
        res.json({ ok: false, error: e.message });
    }
});

app.get('/status', (req, res) => {
    res.json({ ready: isReady });
});

// SECURITY: bind to loopback only so the API is not reachable from the LAN.
app.listen(3001, '127.0.0.1', () => {
    console.log('WhatsApp service running on 127.0.0.1:3001 (token-protected)');
});

client.initialize();
