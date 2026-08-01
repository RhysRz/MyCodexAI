# MyCodexAI Cloud (ไม่ใช้บัตรเครดิต)

สถาปัตยกรรมนี้ย้ายหน้าเว็บ ล็อกอิน แชท ประวัติ ไฟล์ชั่วคราว และคิวงานไป Cloudflare ส่วนงานแก้โค้ดใช้ GitHub Actions แบบทีละงานและเปิด Pull Request ให้ตรวจสอบก่อน Merge เครื่องส่วนตัวจึงไม่ต้องเปิดเซิร์ฟเวอร์หรือ Ollama ไว้ตลอดเวลา

## สิ่งที่อยู่บนคลาวด์

- Cloudflare Worker: API และหน้าเว็บแบบ responsive/PWA
- Workers AI: แชทภาษาไทยและร่างการแก้โค้ด
- D1: บัญชี เซสชัน ประวัติแชท งาน Audit และไฟล์ชั่วคราว
- Cloudflare Queue: คิว Agent แบบ `max_concurrency = 1`
- GitHub Actions: checkout โปรเจกต์ ทดสอบ สร้าง branch และเปิด Pull Request

ข้อจำกัดของรุ่นฟรี: ไฟล์แนบไม่เกิน 10 MB ต่อไฟล์ รวม 50 MB ต่อบัญชีและหมดอายุใน 7 วัน งาน Agent จะรอตามคิวของ repository ส่วนตัวนี้ ไม่ใช่คิวจากผู้ใช้ Workers AI คนอื่นโดยตรง เมื่อโควต้าของผู้ให้บริการหมด ระบบจะหยุดรอรอบรีเซ็ตและไม่คิดเงินหากไม่ได้ผูกวิธีชำระเงิน

## 1. เตรียม GitHub แบบ Private

1. สร้าง repository ใหม่และเลือก **Private** เช่น `MyCodexAI` โดยไม่ต้องสร้าง README ซ้ำ
2. ห้ามอัปโหลด `.env`, `workspace`, `venv`, ฐานข้อมูล, token หรือไฟล์ผู้ใช้ `.gitignore` ของโปรเจกต์กันรายการเหล่านี้ไว้แล้ว
3. เมื่อ local baseline ผ่านการตรวจ ให้ push branch `main` ขึ้น repository นี้
4. สร้าง Fine-grained personal access token จำกัดเฉพาะ repository นี้ และให้สิทธิ์ **Contents: Read and write** เพื่อให้ Worker เรียก `repository_dispatch` ได้

## 2. สร้างทรัพยากร Cloudflare ฟรี

ติดตั้ง Node.js LTS แล้วเปิด PowerShell ใหม่ จากนั้น:

```powershell
cd C:\MyCodexAI\cloud\worker
npm install
npx wrangler login
npx wrangler d1 create mycodexai-cloud
npx wrangler queues create mycodexai-agent
npx wrangler queues create mycodexai-agent-dlq
```

คำสั่ง D1 จะแสดง `database_id` ให้เก็บไว้ จากนั้นตั้ง config โดยไม่ต้องใส่ secret ลงไฟล์:

```powershell
cd C:\MyCodexAI
.\deploy\Set-MyCodexAICloudConfig.ps1 -DatabaseId "D1_DATABASE_ID" -GitHubOwner "GITHUB_USERNAME" -GitHubRepo "PRIVATE_REPOSITORY"
```

## 3. ตั้ง secrets อย่างปลอดภัย

สร้างค่าสุ่มคนละค่ากันอย่างน้อย 32 bytes สำหรับ `RUNNER_CALLBACK_SECRET` และ `CLOUD_BOOTSTRAP_TOKEN` อย่าส่งค่าเหล่านี้ในแชทหรือบันทึกใน source code

```powershell
cd C:\MyCodexAI\cloud\worker
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put RUNNER_CALLBACK_SECRET
npx wrangler secret put CLOUD_BOOTSTRAP_TOKEN
```

Wrangler จะให้พิมพ์ค่าแบบไม่บันทึกลง repository

## 4. Deploy ครั้งแรก

```powershell
cd C:\MyCodexAI
.\deploy\Deploy-MyCodexAICloud.ps1
```

จด URL เช่น `https://mycodexai-cloud.<subdomain>.workers.dev` แล้วอัปเดต `PUBLIC_ORIGIN` ใน `cloud/worker/wrangler.jsonc` เป็น URL นั้น ก่อน Deploy ซ้ำ แม้ระบบ CSRF จะตรวจ origin ของ request อยู่แล้ว แต่การตั้งค่านี้ทำให้ configuration ชัดเจน

## 5. เชื่อม GitHub Actions

ใน private repository ไปที่ **Settings → Secrets and variables → Actions** แล้วเพิ่ม:

- `MYCODEXAI_CLOUD_URL`: workers.dev URL ไม่มี `/` ท้าย
- `MYCODEXAI_RUNNER_SECRET`: ค่าเดียวกับที่ใส่ให้ Wrangler ในขั้นก่อน

ไม่ต้องเพิ่ม `GITHUB_TOKEN`; GitHub สร้าง token อายุสั้นให้ workflow เอง เปิด **Settings → Actions → General → Workflow permissions** เป็น **Read and write permissions** และอนุญาตให้ Actions สร้าง Pull Request หาก repository ปิดสิทธิ์นี้ไว้

## 6. สร้างบัญชีผู้ดูแลครั้งแรก

เปิด workers.dev URL หน้าแรกจะแสดงฟอร์มสร้าง Admin ให้กำหนดชื่อผู้ใช้และรหัสผ่านใหม่อย่างน้อย 12 ตัวอักษร พร้อมใส่ `CLOUD_BOOTSTRAP_TOKEN` ครั้งเดียว หลังมี Admin แล้ว endpoint bootstrap จะปฏิเสธการสร้างบัญชีเพิ่ม

บัญชี Cloud เป็นบัญชีใหม่ รหัส Argon2 ของระบบ Local จะไม่ถูกคัดลอกหรือถอดรหัส ผู้ใช้ทั่วไปต้องรับลิงก์เชิญแบบใช้ครั้งเดียวจากหน้า Admin

## การย้อนกลับ

ก่อนเริ่มงานได้สร้าง checkpoint ไว้ที่:

`C:\MyCodexAI\.mycodexai\checkpoints\pre-cloud-migration-20260802-003002.zip`

การเพิ่มโฟลเดอร์ `cloud`, workflow และไฟล์ deploy ไม่เปลี่ยนฐานข้อมูลหรือ `.env` ของระบบ Local จึงสามารถใช้ระบบเดิมต่อได้จนกว่า Cloud จะผ่านการทดสอบจริง
