const loadProteinsTable = () => {
  let proteinsTable = $("#proteins-table").DataTable({
    dom: "iftplr",
    pageLength: 50,
    language: {
        searchPlaceholder: "Search",
        search: "",
    },
  });

  // Letter button click event
  $(".letter-btn").on("click", function () {
    let letter = $(this).data("letter");
    if (letter === "all") {
      proteinsTable.column(0).search("").draw(); // Show all if "All" is clicked
    } else if (letter === "0-9") {
      proteinsTable.column(0).search("^[0-9]", true, false).draw(); // Show numeric values
    } else {
      proteinsTable.column(0).search("^" + letter, true, false).draw(); // Filter by first letter
    }

    // Remove active class from all buttons, then add to the clicked one
    $(".letter-btn").removeClass("active");
    $(this).addClass("active");
  });

  // Emulate user click on the "A" button
  $(".letter-btn[data-letter='A']").trigger("click");
};

$(document).ready(() => {
  loadProteinsTable();
});
