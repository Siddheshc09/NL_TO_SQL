async function generateSQL() {

    const schemaText = document.getElementById("schema").value;
    const question = document.getElementById("question").value;
    const loading = document.getElementById("loading");
    const resultBox = document.getElementById("result");

    loading.classList.remove("hidden");
    resultBox.innerText = "";

    try {
        const response = await fetch("/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                db_schema: JSON.parse(schemaText),
                question: question
            })
        });

        const data = await response.json();

        if (data.success) {
            resultBox.innerText = data.generated_sql;
        } else {
            resultBox.innerText = "Error: " + data.error;
        }

    } catch (error) {
        resultBox.innerText = "Server Error: " + error;
    }

    loading.classList.add("hidden");
}
