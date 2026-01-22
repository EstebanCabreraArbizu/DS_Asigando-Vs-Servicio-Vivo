const JavaScriptObfuscator = require('javascript-obfuscator');
const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, '../dashboard/static/dashboard/src');
const destDir = path.join(__dirname, '../dashboard/static/dashboard');

if (!fs.existsSync(srcDir)) {
    console.error('Source directory not found:', srcDir);
    process.exit(1);
}

const files = ['upload.js', 'main.js'];

files.forEach(file => {
    const srcPath = path.join(srcDir, file);
    const destPath = path.join(destDir, file);

    if (fs.existsSync(srcPath)) {
        console.log(`Processing ${file}...`);
        const content = fs.readFileSync(srcPath, 'utf8');

        try {
            const obfuscationResult = JavaScriptObfuscator.obfuscate(content, {
                compact: true,
                controlFlowFlattening: true,
                controlFlowFlatteningThreshold: 0.75,
                numbersToExpressions: true,
                simplify: true,
                stringArrayShuffle: true,
                splitStrings: true,
                stringArrayThreshold: 0.75
            });

            fs.writeFileSync(destPath, obfuscationResult.getObfuscatedCode());
            console.log(`Successfully obfuscated ${file}`);
        } catch (error) {
            console.error(`Error obfuscating ${file}:`, error);
            process.exit(1);
        }
    } else {
        console.warn(`File not found: ${file}`);
    }
});
