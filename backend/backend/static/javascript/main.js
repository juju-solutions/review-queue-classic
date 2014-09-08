var states = {
  'pending': 'This item pending a review. If you are the owner, sit tight and someone will review shortly!',
  'followup': 'The author has replied since the review of this item.',
  'ready': 'Your merge has been approved and will land in the charm store soon!',
  'abandonded': 'This has been marked as abandonded and is no longer considered a valid review',
  'reviewed': 'Feedback by the charm community has been placed and follow up by the author is required',
  'inprogress': 'Review has been passed and the item needs more work by the author',
  'closed': 'This review has been completed and the charm in the store!',
  'merged': 'This fix has landed and is in the charm store!'
};

var message = function(type, title, content) {
  var t = $('.message.template').clone(true);
  t.removeClass('template hidden')
  t.addClass(type+' visible');
  t.find('.header').text(title);
  t.find('.content').text(content);
  t.find('.close').bind('click', function() {
    $(this).closest('.message').fadeOut();
  });
  t.appendTo('.messages');
};

$(function() {
  $('table').tablesort();
  $('.ui.checkbox').checkbox();
  $('.ui.checkbox input')
    .change(function() {
      $(this)
        .parents()
        .eq(3)
        .find('.' + $(this).attr('name'))
        .toggle()
      ;
    })
  ;
  $('h1 .icon.filter')
    .click(function() {
      $(this)
        .closest('.review')
        .children('.filter.controls')
        .slideToggle()
      ;
    })
  ;
  $('.review .state').each(function() {
    $(this).data('content', states[$(this).data('sort-value').toLowerCase()]);
    $(this).data('title', $(this).text());
  });
  $('.state').popup();
  $('[data-content]').popup();
  $('.user.select')
    .select2({
      minimumInputLength: 2,
      multiple: true,
      ajax: {
        url: '/user/+search',
        dataType: 'json',
        data: function (term) {
          return {
            q: term
          };
        },
        results: function (data, page) {
          return {results: data};
        }
      },
      initSelection: function(element, callback) {
        var refresh = function(id, next) {
          console.log(id);
          $.ajax("/user/id/"+id, {
            dataType: 'json'
          }).done(function(data) { next(null, data); });
        };

        var ids = $(element).val().split(',');

        if(ids) {
          async.map(ids, refresh, function(err, data) {
            console.log(data);
            callback(data);
          });
        }
      },
      formatResult: function(data) {
        var markup = "<div>" + data.name + "</div>";
        return markup;
      },
      formatSelection: function(data) {
        return data.name
      },
      dropdownCssClass: "bigdrop",
      escapeMarkup: function (m) { return m; }
    })
  ;
  $('select.select').select2();
  $('.locker.icon').click(function() {
    var review_id = $(this).data('review-id');
    var self = $(this);
    self.addClass('loading');

    $.ajax("/review/"+review_id+"/lock", {
      dataType: 'json'
    }).done(function(data) {
      self.removeClass('loading');
      if(data.error) {
        message('error', 'Failed to lock', data.error);
      } else {
        self.toggleClass('unlock lock');
      };
    });
  });
});
