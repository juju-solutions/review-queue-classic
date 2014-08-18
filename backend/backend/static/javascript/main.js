$(function() {
  $('table').tablesort();
  $('.ui.checkbox').checkbox();
  $('.ui.checkbox input').change(function() {
    $(this).parents().eq(3).find('.' + $(this).attr('name')).toggle();
  });
  $('h1 .icon.filter').click(function() {
    $(this).closest('.review').children('.filter.controls').slideToggle();
  });
});
