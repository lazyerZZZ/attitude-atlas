const { chromium } = require("playwright-core");
const assert = require("node:assert/strict");
const { readFile } = require("node:fs/promises");

async function main() {
  const base = process.env.ATLAS_URL || "http://127.0.0.1:8000/";
  const browser = await chromium.launch({executablePath:process.env.CHROME_BIN,headless:true});
  try {
    const context = await browser.newContext({permissions:["clipboard-read","clipboard-write"]});
    const page = await context.newPage();
    const errors=[];
    page.on("pageerror",error=>errors.push(error.message));
    await page.goto(base);
    await page.getByRole("button",{name:"Quaternion",exact:true}).click();
    const message="x: 0\ny: 0\nz: 0\nw: 100";
    await page.locator("#input").fill(message);
    await page.locator("#format").selectOption("ros");
    assert.equal(await page.locator("#input").inputValue(), message);
    await page.locator("#apply").click();
    assert.match(await page.locator("#input-norm").innerText(),/100.*99/);

    await page.getByRole("link",{name:"Bridge check"}).click();
    assert.equal(await page.locator("#angle").innerText(),"90.00°");
    assert.equal(await page.locator("#nose").innerText(),"0.00°");
    await page.locator("#example").selectOption("time");
    await page.locator("#copy-pair").click();
    const url=await page.evaluate(()=>navigator.clipboard.readText());
    await page.goto(url);
    assert.equal(await page.locator("#offset").innerText(),"20 ms");
    const download=page.waitForEvent("download");
    await page.locator("#export-pair").click();
    const data=JSON.parse(await readFile(await (await download).path(),"utf8"));
    assert.equal(data.result.timeOffsetMs,20);
    data.result.rotationDeg=180;
    await page.locator("#example").selectOption("roll");
    await page.locator("#case-file").setInputFiles({name:"pair.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(data))});
    await page.waitForFunction(()=>document.querySelector("#offset").textContent==="20 ms");
    assert.equal(await page.locator("#angle").innerText(),"0.00°");
    await page.locator("#ros").fill("broken");
    assert.ok(await page.locator("#result").isHidden());
    await page.getByRole("button",{name:"Compare attitudes",exact:true}).click();
    assert.match(await page.locator("#feedback").innerText(),/ROS input/);
    await page.locator("#example").selectOption("roll");
    await page.setViewportSize({width:375,height:812});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole("link",{name:"Pose explorer",exact:true}).click();
    await page.getByRole("button",{name:"Replay",exact:true}).click();
    await page.locator("#next-sample").click();
    assert.match(await page.locator("#sample-age").innerText(),/Sample 2 of 187/);
    assert.deepEqual(errors,[]);
    console.log("Browser checks passed for both workbenches.");
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
