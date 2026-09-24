import React from "react";

export default function PrivacyPolicy() {
  return (
    <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 20px", fontFamily: "sans-serif", color: "#333", lineHeight: "1.6" }}>
      <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "8px" }}>Privacy Policy</h1>
      <p style={{ color: "#666", fontSize: "0.9rem", marginBottom: "24px" }}>Last updated: September 24, 2026</p>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>1. Introduction</h2>
        <p>
          Welcome to <strong>Siyaf</strong>. We respect your privacy and are committed to protecting your personal data. 
          This Privacy Policy explains how we collect, use, and process information when you interact with our platform 
          and WhatsApp messaging integrations.
        </p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>2. Information We Collect</h2>
        <p>We may collect minimal personal information to provide our autonomous agent SaaS services, including:</p>
        <ul style={{ paddingLeft: "20px", marginTop: "8px" }}>
          <li>Contact details such as name, email address, and phone number.</li>
          <li>WhatsApp Business Account profile data strictly necessary for webhook operations and message delivery.</li>
          <li>System and usage data to monitor API performance and service health.</li>
        </ul>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>3. How We Use Your Data</h2>
        <p>Your data is processed strictly for the following purposes:</p>
        <ul style={{ paddingLeft: "20px", marginTop: "8px" }}>
          <li>Executing WhatsApp messaging workflows and AI agent integrations on your behalf.</li>
          <li>Authenticating your account and verifying platform setup.</li>
          <li>Maintaining service stability, customer support, and API infrastructure.</li>
        </ul>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>4. Data Deletion & Retention</h2>
        <p>
          We retain user data only as long as necessary to provide our services. Users can request complete deletion 
          of their personal and messaging data at any time by contacting our support team at{" "}
          <a href="mailto:oursaasstartup@gmail.com" style={{ color: "#0066cc" }}>oursaasstartup@gmail.com</a>.
        </p>
      </section>

      <section style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>5. Contact Us</h2>
        <p>If you have any questions or requests regarding this Privacy Policy, please contact us at:</p>
        <p style={{ marginTop: "8px" }}>
          <strong>Siyaf Support</strong><br />
          Email: <a href="mailto:oursaasstartup@gmail.com" style={{ color: "#0066cc" }}>oursaasstartup@gmail.com</a>
        </p>
      </section>
    </main>
  );
}