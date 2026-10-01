from flask import Flask
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/search")
def search():

    query = request.args.get("q")

    results = search_web(query)

    if current_user.is_authenticated:
        history = SearchHistory(
            user_id=current_user.id,
            query=query
        )

        db.session.add(history)
        db.session.commit()

    return jsonify(results)


@app.route("/editor")
@login_required
def editor():
    return render_template("editor.html")


@app.route("/run", methods=["POST"])
def run_code():

    data = request.get_json()

    code = data.get("code")

    result = run_python_code(code)

    return jsonify(result)


if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)