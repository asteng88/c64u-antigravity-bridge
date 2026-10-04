# Security Policy

The **C64U Antigravity Bridge** connects development workstations and AI agent environments directly to physical Commodore 64 Ultimate (C64U) and Ultimate 64 hardware over a local network connection.

Because the bridge possesses Direct Memory Access (DMA) capabilities and can execute arbitrary machine code on the target C64 hardware, please review the security considerations below.

---

## Network Architecture & Threat Model

* **Local Network Device**: The Commodore 64 Ultimate's REST API is designed for trusted local area networks (LANs). It does not employ HTTPS/TLS encryption or enterprise-grade access control by default.
* **DMA & Execution Capabilities**: Any client with network access to the C64U HTTP port can read and write arbitrary RAM, I/O registers, and execute compiled 6502/6510 machine code directly on the physical processor.
* **No Internet Exposure**: **Never expose the C64U REST interface (typically port 80) directly to the public Internet or unsegmented untrusted networks.** Always run behind a secure router or local development subnet.

---

## Best Practices

1. **Use Trusted Networks**: Run the bridge and your C64U device on a secure, private local network or isolated VLAN.
2. **Enable Device Authentication**: If your Ultimate firmware version supports network passwords or access control for the Web Remote Control Service, enable it and configure `C64U_PASSWORD` in your local `.env` file.
3. **Review AI-Generated Code**: While 6502 code executing on a Commodore 64 cannot directly infect the host computer, reviewing generated assembly and POKE operations is recommended to avoid unwanted infinite loops, memory corruption of loaded resident tools, or unexpected hardware state resets.
4. **Protect Environment Secrets**: Ensure your `.env` file containing any network credentials or local configuration remains uncommitted and listed in `.gitignore`.

---

## Reporting Security Vulnerabilities

If you discover a security vulnerability in the bridge software (such as command injection in the CLI/TUI, path traversal, or MCP server handling vulnerabilities):

* Please report it responsibly by contacting the repository maintainer directly via GitHub or opening a private security advisory through the repository's **Security** tab.
* Provide a clear description of the issue, affected versions, and steps to reproduce.
* Please allow reasonable time to review and address the report before public disclosure.
