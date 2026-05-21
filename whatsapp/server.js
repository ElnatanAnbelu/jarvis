const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const { execSync } = require('child_process');
const path = require('path');

const app = express();
app.use(express.json());

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
    puppeteer: { args: ['--no-sandbox', '--disable-setuid-sandbox'] }
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
        const response = await fetch('http://localhost:8080/api/whatsapp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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

app.listen(3001, () => {
    console.log('WhatsApp service running on port 3001');
});

client.initialize();
